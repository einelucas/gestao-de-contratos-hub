"""API de equipes de notificação e vínculo com contratos (Etapa 7), contra Postgres real."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.contracts import Sector, Supplier, UserSectorPermission
from app.modules.contracts.rules import contracts_today

URL = "/api/v1/equipes-notificacao"


async def _sectors(db_session) -> dict[str, str]:
    obras = Sector(slug="obras", name="Obras", acronym="OBR")
    ti = Sector(slug="ti", name="TI", acronym="TI")
    db_session.add_all([obras, ti, Supplier(name="Fornecedor X")])
    await db_session.commit()
    return {"obras": obras.id, "ti": ti.id}


async def _create(client, auth_header, sector_id: str, name: str = "Equipe Obras", members=None):
    body = {
        "name": name,
        "sectorId": sector_id,
        "members": members if members is not None else [{"email": "Ana@Empresa.com", "name": "Ana"}],
    }
    return await client.post(URL, json=body, headers=auth_header("ADMIN"))


async def test_admin_creates_and_manages_team(client, auth_header, db_session) -> None:
    sectors = await _sectors(db_session)
    created = await _create(client, auth_header, sectors["obras"])
    assert created.status_code == 201
    team = created.json()
    assert (team["name"], team["sectorName"], team["active"], team["activeMemberCount"]) == (
        "Equipe Obras",
        "Obras",
        True,
        1,
    )
    assert team["members"][0]["email"] == "ana@empresa.com"  # normalizado

    member_id = team["members"][0]["id"]
    replaced = await client.put(
        f"{URL}/{team['id']}/membros",
        json={
            "members": [
                {"id": member_id, "email": "ana@empresa.com", "name": "Ana", "active": False},
                {"email": "bruno@empresa.com"},
                {"email": "carla@empresa.com"},
            ]
        },
        headers=auth_header("ADMIN"),
    )
    assert replaced.status_code == 200
    assert replaced.json()["activeMemberCount"] == 2

    removed = await client.put(
        f"{URL}/{team['id']}/membros",
        json={"members": [{"email": "bruno@empresa.com"}]},
        headers=auth_header("ADMIN"),
    )
    assert [m["email"] for m in removed.json()["members"]] == ["bruno@empresa.com"]

    renamed = await client.patch(
        f"{URL}/{team['id']}",
        json={"name": "Equipe Contratos — Obras", "active": False},
        headers=auth_header("ADMIN"),
    )
    assert (renamed.json()["name"], renamed.json()["active"]) == ("Equipe Contratos — Obras", False)

    actions = (await db_session.execute(select(AuditLog.action).order_by(AuditLog.createdAt))).scalars().all()
    assert actions == [
        "notification_team.create",
        "notification_team.members.replace",
        "notification_team.members.replace",
        "notification_team.update",
    ]
    entry = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(AuditLog.action == "notification_team.members.replace")
                .order_by(AuditLog.createdAt)
            )
        )
        .scalars()
        .first()
    )
    assert entry.metadata_ == {"added": ["bruno@empresa.com", "carla@empresa.com"], "removed": []}


async def test_member_validation(client, auth_header, db_session) -> None:
    sectors = await _sectors(db_session)
    invalid = await _create(client, auth_header, sectors["obras"], members=[{"email": "sem-arroba"}])
    assert invalid.status_code == 422
    assert "E-mail inválido" in invalid.text
    empty = await _create(client, auth_header, sectors["obras"], members=[{"email": "  "}])
    assert empty.status_code == 422
    duplicated = await _create(
        client,
        auth_header,
        sectors["obras"],
        members=[{"email": "a@empresa.com"}, {"email": "A@EMPRESA.COM "}],
    )
    assert duplicated.status_code == 422
    assert "repetido" in duplicated.text

    assert (await _create(client, auth_header, sectors["obras"])).status_code == 201
    same_name = await _create(client, auth_header, sectors["obras"])
    assert same_name.status_code == 409


async def test_team_permissions_by_role(client, auth_header, db_session) -> None:
    sectors = await _sectors(db_session)
    obras = (await _create(client, auth_header, sectors["obras"])).json()
    ti = (await _create(client, auth_header, sectors["ti"], name="Equipe TI")).json()

    # VIEWER não administra nem consulta equipes.
    assert (await client.get(URL, headers=auth_header("VIEWER"))).status_code == 403
    assert (
        await client.post(
            URL, json={"name": "x", "sectorId": sectors["obras"]}, headers=auth_header("VIEWER")
        )
    ).status_code == 403

    # ANALYST consulta só equipes dos setores em que pode editar, e não administra.
    analyst_id = (await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))).json()["id"]
    db_session.add(
        UserSectorPermission(userId=analyst_id, sectorId=sectors["obras"], canView=True, canEdit=True)
    )
    db_session.add(
        UserSectorPermission(userId=analyst_id, sectorId=sectors["ti"], canView=True, canEdit=False)
    )
    await db_session.commit()
    listed = (await client.get(URL, headers=auth_header("ANALYST"))).json()["items"]
    assert [team["id"] for team in listed] == [obras["id"]]
    assert (await client.get(f"{URL}/{ti['id']}", headers=auth_header("ANALYST"))).status_code == 404
    assert (
        await client.patch(f"{URL}/{obras['id']}", json={"active": False}, headers=auth_header("ANALYST"))
    ).status_code == 403
    assert (
        await client.put(f"{URL}/{obras['id']}/membros", json={"members": []}, headers=auth_header("ANALYST"))
    ).status_code == 403

    # ADMIN vê todas.
    assert len((await client.get(URL, headers=auth_header("ADMIN"))).json()["items"]) == 2


async def test_contract_team_must_match_sector_and_have_recipients(client, auth_header, db_session) -> None:
    sectors = await _sectors(db_session)
    obras_team = (await _create(client, auth_header, sectors["obras"])).json()
    ti_team = (await _create(client, auth_header, sectors["ti"], name="Equipe TI")).json()
    empty_team = (
        await _create(client, auth_header, sectors["obras"], name="Equipe vazia", members=[])
    ).json()
    end = (contracts_today() + timedelta(days=90)).isoformat()
    base = {"sectorId": sectors["obras"], "supplier": "Fornecedor X", "endDate": end}

    other_sector = await client.post(
        "/api/v1/contratos",
        json={**base, "contractNumber": "1", "notificationTeamId": ti_team["id"]},
        headers=auth_header("ADMIN"),
    )
    assert other_sector.status_code == 422
    assert "outro setor" in other_sector.json()["error"]

    no_team = await client.post(
        "/api/v1/contratos",
        json={**base, "contractNumber": "2", "notify": True},
        headers=auth_header("ADMIN"),
    )
    assert no_team.status_code == 422

    no_members = await client.post(
        "/api/v1/contratos",
        json={
            **base,
            "contractNumber": "3",
            "notify": True,
            "notificationTeamId": empty_team["id"],
        },
        headers=auth_header("ADMIN"),
    )
    assert no_members.status_code == 422

    ok = await client.post(
        "/api/v1/contratos",
        json={
            **base,
            "contractNumber": "4",
            "notify": True,
            "notificationTeamId": obras_team["id"],
        },
        headers=auth_header("ADMIN"),
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["notificationTeamName"] == "Equipe Obras"
    assert body["notificationRecipients"] == ["ana@empresa.com"]
    assert body["notifyEnabledOn"] == contracts_today().isoformat()

    # Sem alertas, a equipe é opcional.
    silent = await client.post(
        "/api/v1/contratos", json={**base, "contractNumber": "5"}, headers=auth_header("ADMIN")
    )
    assert silent.status_code == 201 and silent.json()["notify"] is False

    duplicated = await client.post(
        "/api/v1/contratos", json={**base, "contractNumber": "4"}, headers=auth_header("ADMIN")
    )
    assert duplicated.status_code == 409
    assert "número" in duplicated.json()["error"]


async def test_sector_change_invalidates_team(client, auth_header, db_session) -> None:
    sectors = await _sectors(db_session)
    obras_team = (await _create(client, auth_header, sectors["obras"])).json()
    ti_team = (await _create(client, auth_header, sectors["ti"], name="Equipe TI")).json()
    created = await client.post(
        "/api/v1/contratos",
        json={
            "sectorId": sectors["obras"],
            "supplier": "Fornecedor X",
            "contractNumber": "10",
            "notify": True,
            "notificationTeamId": obras_team["id"],
        },
        headers=auth_header("ADMIN"),
    )
    url = f"/api/v1/contratos/{created.json()['id']}"

    mismatch = await client.patch(url, json={"sectorId": sectors["ti"]}, headers=auth_header("ADMIN"))
    assert mismatch.status_code == 422

    moved = await client.patch(
        url,
        json={"sectorId": sectors["ti"], "notificationTeamId": ti_team["id"]},
        headers=auth_header("ADMIN"),
    )
    assert moved.status_code == 200
    assert (moved.json()["sectorId"], moved.json()["notificationTeamName"]) == (
        sectors["ti"],
        "Equipe TI",
    )

    # Equipe vinculada a contrato não muda de setor.
    blocked = await client.patch(
        f"{URL}/{ti_team['id']}", json={"sectorId": sectors["obras"]}, headers=auth_header("ADMIN")
    )
    assert blocked.status_code == 409


async def test_disabling_alerts_clears_enabled_date(client, auth_header, db_session) -> None:
    sectors = await _sectors(db_session)
    team = (await _create(client, auth_header, sectors["obras"])).json()
    created = await client.post(
        "/api/v1/contratos",
        json={
            "sectorId": sectors["obras"],
            "supplier": "F",
            "contractNumber": "1",
            "notificationTeamId": team["id"],
        },
        headers=auth_header("ADMIN"),
    )
    url = f"/api/v1/contratos/{created.json()['id']}"
    assert created.json()["notifyEnabledOn"] is None
    on = await client.patch(url, json={"notify": True}, headers=auth_header("ADMIN"))
    assert on.json()["notifyEnabledOn"] == contracts_today().isoformat()
    off = await client.patch(url, json={"notify": False}, headers=auth_header("ADMIN"))
    assert off.json()["notifyEnabledOn"] is None


async def test_patch_team_with_members_is_atomic(client, auth_header, db_session) -> None:
    """Equipe + membros no mesmo PATCH: ou salva tudo, ou nada (sem salvamento parcial)."""
    sectors = await _sectors(db_session)
    team = (await _create(client, auth_header, sectors["obras"])).json()
    url = f"{URL}/{team['id']}"

    saved = await client.patch(
        url,
        json={
            "name": "Equipe Renomeada",
            "members": [{"email": "novo@empresa.com", "name": "Novo"}],
        },
        headers=auth_header("ADMIN"),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Equipe Renomeada"
    assert [m["email"] for m in saved.json()["members"]] == ["novo@empresa.com"]

    # Membro inválido (id de outra equipe): nada é gravado, nem o nome.
    failed = await client.patch(
        url,
        json={
            "name": "Nome Que Não Pode Ficar",
            "members": [{"id": "inexistente", "email": "x@empresa.com"}],
        },
        headers=auth_header("ADMIN"),
    )
    assert 400 <= failed.status_code < 500
    current = (await client.get(url, headers=auth_header("ADMIN"))).json()
    assert current["name"] == "Equipe Renomeada"
    assert [m["email"] for m in current["members"]] == ["novo@empresa.com"]

    duplicated = await client.patch(
        url,
        json={"members": [{"email": "a@empresa.com"}, {"email": "A@empresa.com"}]},
        headers=auth_header("ADMIN"),
    )
    assert duplicated.status_code == 422

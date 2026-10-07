"""Escopo por setor (UserSectorPermission) e campos de alerta em /contratos."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.contracts import (
    Contract,
    NotificationTeam,
    NotificationTeamMember,
    Sector,
    Supplier,
    UserSectorPermission,
)


async def _user_id(client, auth_header, role: str) -> str:
    response = await client.get("/api/v1/auth/me", headers=auth_header(role))
    return response.json()["id"]


async def _seed(db_session) -> dict[str, str]:
    """Dois setores com um contrato cada."""
    obras = Sector(slug="obras", name="Obras", acronym="OBR")
    ti = Sector(slug="ti", name="TI", acronym="TI")
    supplier = Supplier(name="Fornecedor X")
    db_session.add_all([obras, ti, supplier])
    await db_session.flush()
    c_obras = Contract(
        sectorId=obras.id, supplierId=supplier.id, contractNumber="100", endDate=date(2030, 1, 1)
    )
    c_ti = Contract(sectorId=ti.id, supplierId=supplier.id, contractNumber="200", endDate=date(2030, 1, 1))
    db_session.add_all([c_obras, c_ti])
    await db_session.commit()
    return {"obras": obras.id, "ti": ti.id, "c_obras": c_obras.id, "c_ti": c_ti.id}


async def _grant(db_session, user_id: str, sector_id: str, *, can_edit: bool = False) -> None:
    db_session.add(UserSectorPermission(userId=user_id, sectorId=sector_id, canView=True, canEdit=can_edit))
    await db_session.commit()


async def test_user_without_sector_permission_sees_nothing(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)

    listed = await client.get("/api/v1/contratos", headers=auth_header("VIEWER"))
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    sectors = await client.get("/api/v1/setores", headers=auth_header("VIEWER"))
    assert sectors.json()["items"] == []

    detail = await client.get(f"/api/v1/contratos/{ids['c_obras']}", headers=auth_header("VIEWER"))
    assert detail.status_code == 404


async def test_viewer_sees_only_permitted_sector(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    viewer_id = await _user_id(client, auth_header, "VIEWER")
    await _grant(db_session, viewer_id, ids["obras"])

    listed = await client.get("/api/v1/contratos", headers=auth_header("VIEWER"))
    items = listed.json()["items"]
    assert [item["contractNumber"] for item in items] == ["100"]
    assert items[0]["canEdit"] is False

    # Filtro por setor não permitido não vaza nada.
    other = await client.get(f"/api/v1/contratos?sectorId={ids['ti']}", headers=auth_header("VIEWER"))
    assert other.json()["total"] == 0

    hidden = await client.get(f"/api/v1/contratos/{ids['c_ti']}", headers=auth_header("VIEWER"))
    assert hidden.status_code == 404

    sectors = await client.get("/api/v1/setores", headers=auth_header("VIEWER"))
    assert [s["slug"] for s in sectors.json()["items"]] == ["obras"]


async def test_viewer_cannot_edit_even_with_can_edit_flag(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    viewer_id = await _user_id(client, auth_header, "VIEWER")
    await _grant(db_session, viewer_id, ids["obras"], can_edit=True)

    response = await client.patch(
        f"/api/v1/contratos/{ids['c_obras']}", json={"unit": "LEM"}, headers=auth_header("VIEWER")
    )
    assert response.status_code == 403


async def test_analyst_edits_only_sectors_with_can_edit(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    analyst_id = await _user_id(client, auth_header, "ANALYST")
    await _grant(db_session, analyst_id, ids["obras"], can_edit=True)
    await _grant(db_session, analyst_id, ids["ti"], can_edit=False)

    allowed = await client.patch(
        f"/api/v1/contratos/{ids['c_obras']}", json={"unit": "LEM"}, headers=auth_header("ANALYST")
    )
    assert allowed.status_code == 200
    assert allowed.json()["unit"] == "LEM"
    assert allowed.json()["canEdit"] is True

    view_only = await client.patch(
        f"/api/v1/contratos/{ids['c_ti']}", json={"unit": "LEM"}, headers=auth_header("ANALYST")
    )
    assert view_only.status_code == 403

    create_denied = await client.post(
        "/api/v1/contratos",
        json={"sectorId": ids["ti"], "supplier": "Y", "contractNumber": "300"},
        headers=auth_header("ANALYST"),
    )
    assert create_denied.status_code == 403

    create_ok = await client.post(
        "/api/v1/contratos",
        json={"sectorId": ids["obras"], "supplier": "Y", "contractNumber": "300"},
        headers=auth_header("ANALYST"),
    )
    assert create_ok.status_code == 201


async def test_access_lifecycle_view_edit_revoke(client, auth_header, db_session) -> None:
    """Ciclo completo: só consulta -> 403 no PATCH -> ganha canEdit -> edita -> perde acesso -> 404."""
    ids = await _seed(db_session)
    analyst_id = await _user_id(client, auth_header, "ANALYST")
    url = f"/api/v1/contratos/{ids['c_obras']}"
    permissions_url = f"/api/v1/usuarios/{analyst_id}/setores"

    # 1. canView=true, canEdit=false
    granted = await client.put(
        permissions_url,
        json={"items": [{"sectorId": ids["obras"], "canView": True, "canEdit": False}]},
        headers=auth_header("ADMIN"),
    )
    assert granted.status_code == 200

    # 2. consegue consultar
    detail = await client.get(url, headers=auth_header("ANALYST"))
    assert detail.status_code == 200
    assert detail.json()["canEdit"] is False

    # 3. 403 no PATCH
    denied = await client.patch(url, json={"unit": "LEM"}, headers=auth_header("ANALYST"))
    assert denied.status_code == 403

    # 4. ADMIN libera edição
    await client.put(
        permissions_url,
        json={"items": [{"sectorId": ids["obras"], "canView": True, "canEdit": True}]},
        headers=auth_header("ADMIN"),
    )

    # 5. ANALYST passa a editar
    edited = await client.patch(url, json={"unit": "LEM"}, headers=auth_header("ANALYST"))
    assert edited.status_code == 200
    assert edited.json()["canEdit"] is True

    # 6. ADMIN remove todo o acesso
    await client.put(permissions_url, json={"items": []}, headers=auth_header("ADMIN"))

    # 7. contrato deixa de existir para o ANALYST
    gone = await client.get(url, headers=auth_header("ANALYST"))
    assert gone.status_code == 404
    gone_patch = await client.patch(url, json={"unit": "Balsas"}, headers=auth_header("ANALYST"))
    assert gone_patch.status_code == 404


async def test_admin_sees_and_edits_all(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    await _user_id(client, auth_header, "ADMIN")
    # ADMIN não precisa de nenhuma linha em UserSectorPermission.
    permission_rows = (await db_session.execute(select(UserSectorPermission))).scalars().all()
    assert permission_rows == []

    sectors = await client.get("/api/v1/setores", headers=auth_header("ADMIN"))
    assert {s["slug"] for s in sectors.json()["items"]} == {"obras", "ti"}
    assert all(s["canEdit"] for s in sectors.json()["items"])

    detail = await client.get(f"/api/v1/contratos/{ids['c_ti']}", headers=auth_header("ADMIN"))
    assert detail.status_code == 200

    created = await client.post(
        "/api/v1/contratos",
        json={"sectorId": ids["ti"], "supplier": "Y", "contractNumber": "300"},
        headers=auth_header("ADMIN"),
    )
    assert created.status_code == 201

    listed = await client.get("/api/v1/contratos", headers=auth_header("ADMIN"))
    assert listed.json()["total"] == 3
    assert all(item["canEdit"] for item in listed.json()["items"])

    response = await client.patch(
        f"/api/v1/contratos/{ids['c_ti']}", json={"unit": "Balsas"}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 200


async def _team(db_session, sector_id: str, emails: list[str], name: str = "Equipe Obras") -> str:
    team = NotificationTeam(name=name, sectorId=sector_id, active=True)
    team.members = [NotificationTeamMember(email=email, active=True) for email in emails]
    db_session.add(team)
    await db_session.commit()
    return team.id


async def test_alert_fields_with_notification_team(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    url = f"/api/v1/contratos/{ids['c_obras']}"
    team_id = await _team(db_session, ids["obras"], ["gestor@empresa.com", "apoio@empresa.com"])

    no_team = await client.patch(url, json={"notify": True}, headers=auth_header("ADMIN"))
    assert no_team.status_code == 422

    enabled = await client.patch(
        url,
        json={"notify": True, "notificationTeamId": team_id, "autoRenewal": True, "criticality": "ALTA"},
        headers=auth_header("ADMIN"),
    )
    assert enabled.status_code == 200
    body = enabled.json()
    assert body["notify"] is True
    assert body["notificationTeamName"] == "Equipe Obras"
    assert body["notificationRecipients"] == ["apoio@empresa.com", "gestor@empresa.com"]
    assert body["notificationProblem"] is None
    assert body["autoRenewal"] is True
    assert body["criticality"] == "ALTA"
    # Alertas não mudam o status visual: vencimento em 2030 continua Regular.
    assert body["alert"] == "Regular"

    # Campos legados de responsável/antecedência não são mais aceitos como entrada (ignorados).
    legacy = await client.patch(
        url, json={"responsibleEmail": "x@empresa.com", "noticeDays": 60}, headers=auth_header("ADMIN")
    )
    assert legacy.status_code == 200
    assert (legacy.json()["responsibleEmail"], legacy.json()["noticeDays"]) == (None, 20)


async def test_alert_field_validation(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    url = f"/api/v1/contratos/{ids['c_obras']}"

    for payload in (
        {"notify": None},
        {"sectorId": None},
        {"supplier": None},
        {"criticality": "URGENTE"},
        {"notificationTeamId": "nao-existe"},
    ):
        response = await client.patch(url, json=payload, headers=auth_header("ADMIN"))
        assert response.status_code in (404, 422), payload


async def test_update_records_alert_fields_in_audit(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    team_id = await _team(db_session, ids["obras"], ["gestor@empresa.com"])
    response = await client.patch(
        f"/api/v1/contratos/{ids['c_obras']}",
        json={"notify": True, "notificationTeamId": team_id, "autoRenewal": True, "criticality": "MEDIA"},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200

    entry = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "contract.update"))
    ).scalar_one()
    assert entry.entityId == ids["c_obras"]
    before = entry.previousData
    assert before["notify"] is False
    assert before["notificationTeamId"] is None
    assert before["notifyEnabledOn"] is None
    assert before["autoRenewal"] is False
    assert before["criticality"] is None
    assert entry.newData == {
        "notify": True,
        "notificationTeamId": team_id,
        "autoRenewal": True,
        "criticality": "MEDIA",
    }


async def test_admin_manages_user_sector_permissions(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    viewer_id = await _user_id(client, auth_header, "VIEWER")
    url = f"/api/v1/usuarios/{viewer_id}/setores"

    forbidden = await client.put(url, json={"items": []}, headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403

    replaced = await client.put(
        url,
        json={
            "items": [
                {"sectorId": ids["obras"], "canView": True, "canEdit": False},
                # canEdit sem canView é normalizado para canView=true.
                {"sectorId": ids["ti"], "canView": False, "canEdit": True},
            ]
        },
        headers=auth_header("ADMIN"),
    )
    assert replaced.status_code == 200
    items = {item["sectorId"]: item for item in replaced.json()["items"]}
    assert items[ids["ti"]]["canView"] is True

    listed = await client.get("/api/v1/contratos", headers=auth_header("VIEWER"))
    assert listed.json()["total"] == 2

    duplicated = await client.put(
        url,
        json={"items": [{"sectorId": ids["obras"]}, {"sectorId": ids["obras"]}]},
        headers=auth_header("ADMIN"),
    )
    assert duplicated.status_code == 422

    unknown = await client.put(
        url, json={"items": [{"sectorId": "nao-existe"}]}, headers=auth_header("ADMIN")
    )
    assert unknown.status_code == 422

    cleared = await client.put(url, json={"items": []}, headers=auth_header("ADMIN"))
    assert cleared.json()["items"] == []
    listed = await client.get("/api/v1/contratos", headers=auth_header("VIEWER"))
    assert listed.json()["total"] == 0


async def test_sector_permission_changes_are_audited(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    admin_id = await _user_id(client, auth_header, "ADMIN")
    viewer_id = await _user_id(client, auth_header, "VIEWER")
    url = f"/api/v1/usuarios/{viewer_id}/setores"

    await client.put(url, json={"items": [{"sectorId": ids["obras"]}]}, headers=auth_header("ADMIN"))
    await client.put(
        url, json={"items": [{"sectorId": ids["ti"], "canEdit": True}]}, headers=auth_header("ADMIN")
    )

    entries = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(AuditLog.action == "user.sector_permissions.replace")
                .order_by(AuditLog.createdAt.asc())
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2
    first, second = entries
    assert first.userId == admin_id
    assert first.entity == "User"
    assert first.entityId == viewer_id
    assert first.previousData == []
    assert [(p["sectorId"], p["canView"], p["canEdit"]) for p in first.newData] == [
        (ids["obras"], True, False)
    ]
    assert second.previousData == first.newData
    assert [(p["sectorId"], p["canView"], p["canEdit"]) for p in second.newData] == [(ids["ti"], True, True)]


async def test_sector_permission_endpoints_validate_user(client, auth_header) -> None:
    missing = await client.get("/api/v1/usuarios/nao-existe/setores", headers=auth_header("ADMIN"))
    assert missing.status_code == 404
    missing_put = await client.put(
        "/api/v1/usuarios/nao-existe/setores", json={"items": []}, headers=auth_header("ADMIN")
    )
    assert missing_put.status_code == 404

"""DELETE /contratos/{id}: autorização, cascatas e indicadores."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.contracts import (
    Contract,
    ContractNotification,
    ContractNotificationType,
    OverdueContractTracking,
    Sector,
    Supplier,
    UserSectorPermission,
)
from app.modules.contracts.rules import contracts_today


async def _seed(db_session) -> dict[str, str]:
    today = contracts_today()
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor X")
    db_session.add_all([sector, supplier])
    await db_session.flush()

    deleted = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="DEL-100",
        endDate=today - timedelta(days=10),
        unit="Matriz",
    )
    retained = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="KEEP-200",
        endDate=today + timedelta(days=100),
        unit="Matriz",
    )
    db_session.add_all([deleted, retained])
    await db_session.flush()
    db_session.add_all(
        [
            ContractNotification(
                contractId=deleted.id,
                type=ContractNotificationType.VENCIDO,
                recipient="gestor@empresa.com",
                referenceDate=today,
                contractEndDate=deleted.endDate,
            ),
            OverdueContractTracking(contractId=deleted.id, firstSeenOverdueAt=today),
        ]
    )
    await db_session.commit()
    return {"sector": sector.id, "deleted": deleted.id, "retained": retained.id}


async def _user_id(client, auth_header, role: str) -> str:
    response = await client.get("/api/v1/auth/me", headers=auth_header(role))
    return response.json()["id"]


async def _grant(db_session, user_id: str, sector_id: str, *, can_edit: bool) -> None:
    db_session.add(
        UserSectorPermission(
            userId=user_id,
            sectorId=sector_id,
            canView=True,
            canEdit=can_edit,
        )
    )
    await db_session.commit()


async def test_delete_removes_contract_from_lists_indicators_and_dependencies(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    url = f"/api/v1/contratos/{ids['deleted']}"

    before = await client.get("/api/v1/contratos/resumo", headers=auth_header("ADMIN"))
    assert before.json()["kpis"]["total"] == 2
    assert before.json()["kpis"]["vencido"] == 1
    history_before = await client.get(
        "/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN")
    )
    assert history_before.json()["items"][-1]["remaining"] == 1

    response = await client.delete(url, headers=auth_header("ADMIN"))

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(url, headers=auth_header("ADMIN"))).status_code == 404

    listed = await client.get("/api/v1/contratos", headers=auth_header("ADMIN"))
    assert listed.json()["total"] == 1
    assert [item["id"] for item in listed.json()["items"]] == [ids["retained"]]

    summary = await client.get("/api/v1/contratos/resumo", headers=auth_header("ADMIN"))
    assert summary.json()["kpis"]["total"] == 1
    assert summary.json()["kpis"]["vencido"] == 0
    history_after = await client.get(
        "/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN")
    )
    assert history_after.json()["items"][-1]["remaining"] == 0

    sectors = await client.get("/api/v1/setores", headers=auth_header("ADMIN"))
    assert sectors.json()["items"][0]["contractCount"] == 1

    notifications = (
        await db_session.execute(
            select(ContractNotification).where(ContractNotification.contractId == ids["deleted"])
        )
    ).scalars().all()
    tracking = (
        await db_session.execute(
            select(OverdueContractTracking).where(
                OverdueContractTracking.contractId == ids["deleted"]
            )
        )
    ).scalars().all()
    assert notifications == []
    assert tracking == []

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "contract.delete"))
    ).scalar_one()
    assert audit.entityId == ids["deleted"]
    assert audit.previousData["contractNumber"] == "DEL-100"
    assert audit.newData is None


async def test_delete_requires_contract_management_permission(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    viewer_id = await _user_id(client, auth_header, "VIEWER")
    await _grant(db_session, viewer_id, ids["sector"], can_edit=True)

    response = await client.delete(
        f"/api/v1/contratos/{ids['deleted']}", headers=auth_header("VIEWER")
    )

    assert response.status_code == 403
    assert (await db_session.get(Contract, ids["deleted"])) is not None


async def test_analyst_deletes_only_contracts_in_editable_sectors(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    analyst_id = await _user_id(client, auth_header, "ANALYST")
    await _grant(db_session, analyst_id, ids["sector"], can_edit=False)
    url = f"/api/v1/contratos/{ids['deleted']}"

    denied = await client.delete(url, headers=auth_header("ANALYST"))
    assert denied.status_code == 403

    permission = (
        await db_session.execute(
            select(UserSectorPermission).where(
                UserSectorPermission.userId == analyst_id,
                UserSectorPermission.sectorId == ids["sector"],
            )
        )
    ).scalar_one()
    permission.canEdit = True
    await db_session.commit()

    allowed = await client.delete(url, headers=auth_header("ANALYST"))
    assert allowed.status_code == 204


async def test_delete_unknown_contract_returns_404(client, auth_header) -> None:
    response = await client.delete(
        "/api/v1/contratos/nao-existe", headers=auth_header("ADMIN")
    )
    assert response.status_code == 404

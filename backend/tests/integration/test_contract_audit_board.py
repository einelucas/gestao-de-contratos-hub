"""Kanban de auditoria e sincronização com o status dos contratos."""

from __future__ import annotations

from datetime import timedelta

from app.models.contracts import Contract, Sector, Supplier, UserSectorPermission
from app.modules.contracts.rules import contracts_today

BOARD_URL = "/api/v1/contratos/auditoria"


async def _seed(db_session) -> dict[str, str]:
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor Kanban")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    overdue = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="V-100",
        endDate=contracts_today() - timedelta(days=10),
        unit="Balsas",
    )
    regular = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="R-200",
        endDate=contracts_today() + timedelta(days=100),
        unit="LEM",
    )
    db_session.add_all([overdue, regular])
    await db_session.commit()
    return {"sector": sector.id, "overdue": overdue.id, "regular": regular.id}


async def test_overdue_contract_enters_awaiting_analysis_automatically(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)

    response = await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    assert response.status_code == 200
    assert response.json()["units"] == ["Balsas"]
    assert [(item["id"], item["auditStage"]) for item in response.json()["items"]] == [
        (ids["overdue"], "AGUARDANDO_ANALISE")
    ]


async def test_moving_to_finalized_updates_contract_and_moving_back_reopens_it(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    move_url = f"/api/v1/contratos/{ids['overdue']}/auditoria"

    in_progress = await client.patch(
        move_url, json={"stage": "EM_TRATATIVA"}, headers=auth_header("ADMIN")
    )
    finalized = await client.patch(
        move_url, json={"stage": "FINALIZADO"}, headers=auth_header("ADMIN")
    )
    reopened = await client.patch(
        move_url, json={"stage": "EM_FINALIZACAO"}, headers=auth_header("ADMIN")
    )

    assert in_progress.status_code == 200
    assert in_progress.json()["auditStage"] == "EM_TRATATIVA"
    assert finalized.status_code == 200
    assert finalized.json()["finalized"] is True
    assert finalized.json()["alert"] == "Finalizado"
    assert reopened.status_code == 200
    assert reopened.json()["finalized"] is False
    assert reopened.json()["alert"] == "Vencido"
    assert reopened.json()["auditStage"] == "EM_FINALIZACAO"


async def test_extending_deadline_reopens_contract_and_removes_it_from_board(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    move_url = f"/api/v1/contratos/{ids['overdue']}/auditoria"
    await client.patch(move_url, json={"stage": "FINALIZADO"}, headers=auth_header("ADMIN"))

    extended = await client.patch(
        f"/api/v1/contratos/{ids['overdue']}",
        json={"endDate": (contracts_today() + timedelta(days=120)).isoformat()},
        headers=auth_header("ADMIN"),
    )
    board = await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    assert extended.status_code == 200
    assert extended.json()["finalized"] is False
    assert extended.json()["alert"] == "Regular"
    assert extended.json()["auditStage"] is None
    assert board.json()["items"] == []


async def test_board_and_moves_respect_sector_permissions(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    viewer = await client.get("/api/v1/auth/me", headers=auth_header("VIEWER"))
    viewer_id = viewer.json()["id"]
    db_session.add(
        UserSectorPermission(
            userId=viewer_id, sectorId=ids["sector"], canView=True, canEdit=False
        )
    )
    await db_session.commit()

    board = await client.get(BOARD_URL, headers=auth_header("VIEWER"))
    move = await client.patch(
        f"/api/v1/contratos/{ids['overdue']}/auditoria",
        json={"stage": "EM_TRATATIVA"},
        headers=auth_header("VIEWER"),
    )

    assert board.status_code == 200
    assert board.json()["items"][0]["canEdit"] is False
    assert move.status_code == 403

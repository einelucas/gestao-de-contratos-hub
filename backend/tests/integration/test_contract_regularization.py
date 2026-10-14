"""Regularização persistida e compatibilidade com o Kanban de auditoria."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.contracts import Contract, Sector, Supplier, UserSectorPermission
from app.modules.contracts.rules import contracts_today

URL = "/api/v1/contratos"


async def _seed(db_session) -> str:
    sector = Sector(slug="regularizacao", name="Projetos", acronym="PRO")
    supplier = Supplier(name="Fornecedor regularização")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    contract = Contract(
        sectorId=sector.id, supplierId=supplier.id, contractNumber="REG-100",
        endDate=contracts_today() - timedelta(days=10), unit="Dourados",
    )
    db_session.add(contract)
    await db_session.commit()
    return contract.id


async def _patch(client, auth_header, contract_id, payload, status=200):
    response = await client.patch(
        f"{URL}/{contract_id}", json=payload, headers=auth_header("ADMIN")
    )
    assert response.status_code == status, response.text
    return response.json()


async def _start(client, auth_header, contract_id):
    return await _patch(client, auth_header, contract_id, {
        "regularizationStage": "aguardando_analise", "regularizationResponsible": "Samuel",
    })


async def test_regularization_persists_without_renewing_real_deadline(
    client, auth_header, db_session
) -> None:
    contract_id = await _seed(db_session)
    started = await _start(client, auth_header, contract_id)
    assert started["alert"] == "Regularizacao"
    assert started["situation"] == "Vencido"
    assert started["daysToEnd"] == -10
    assert len(started["regularizationHistory"]) == 1
    datetime.fromisoformat(started["regularizationHistory"][0]["date"])
    again = await client.get(f"{URL}/{contract_id}", headers=auth_header("ADMIN"))
    assert again.json() == started
    report = (await client.get(f"{URL}/resumo", headers=auth_header("ADMIN"))).json()
    assert report["kpis"]["regularization"] == 1
    assert report["kpis"]["vencido"] == 0
    assert report["kpis"]["onTime"] == 0
    assert report["kpis"]["onTimeBase"] == 1
    assert sum(bucket["count"] for bucket in report["deadlines"]) == 1


async def test_movements_append_history_and_repeated_save_is_idempotent(
    client, auth_header, db_session
) -> None:
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    for _ in range(2):
        moved = await _patch(client, auth_header, contract_id, {
            "regularizationStage": "em_tratativa", "regularizationNotes": "Aguardando fornecedor",
        })
        events = moved["regularizationHistory"]
        assert len(events) == 2
        assert events[-1]["previousStage"] == "aguardando_analise"
        assert events[-1]["stage"] == "em_tratativa"


async def test_cannot_clear_overdue_regularization_without_renewal(client, auth_header, db_session) -> None:
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    await _patch(client, auth_header, contract_id, {"regularizationStage": None}, status=422)
    again = await client.get(f"{URL}/{contract_id}", headers=auth_header("ADMIN"))
    assert again.json()["regularizationStage"] == "aguardando_analise"
    assert len(again.json()["regularizationHistory"]) == 1


@pytest.mark.parametrize("explicit_clear", [True, False])
async def test_renewal_completes_both_boards(client, auth_header, db_session, explicit_clear) -> None:
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    payload = {"endDate": (contracts_today() + timedelta(days=100)).isoformat()}
    if explicit_clear:
        payload["regularizationStage"] = None
    result = await _patch(client, auth_header, contract_id, payload)
    assert result["alert"] == "Regular"
    assert result["auditStage"] is None
    assert result["regularizationStage"] is None
    assert result["regularizationHistory"][-1]["stage"] is None


@pytest.mark.parametrize("via_audit", [True, False])
async def test_finalization_clears_regularization_without_reappearing_on_reopen(
    client, auth_header, db_session, via_audit
) -> None:
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    if via_audit:
        closed_response = await client.patch(
            f"{URL}/{contract_id}/auditoria", json={"stage": "FINALIZADO"}, headers=auth_header("ADMIN"),
        )
        assert closed_response.status_code == 200, closed_response.text
        closed = closed_response.json()
    else:
        closed = await _patch(client, auth_header, contract_id, {"finalized": True})
    assert closed["alert"] == "Finalizado"
    assert closed["regularizationStage"] is None
    assert closed["regularizationHistory"][-1]["stage"] is None
    reopened = await _patch(client, auth_header, contract_id, {"finalized": False})
    assert reopened["alert"] == "Vencido"
    assert reopened["regularizationStage"] is None


async def test_invalid_stage_and_finalized_entry_are_rejected(client, auth_header, db_session) -> None:
    contract_id = await _seed(db_session)
    await _patch(client, auth_header, contract_id, {"regularizationStage": "inventado"}, status=422)
    await _patch(client, auth_header, contract_id, {"finalized": True})
    await _patch(client, auth_header, contract_id, {"regularizationStage": "em_tratativa"}, status=422)


async def test_regularization_respects_sector_edit_permissions(client, auth_header, db_session) -> None:
    contract_id = await _seed(db_session)
    contract = await db_session.get(Contract, contract_id)
    viewer = await client.get("/api/v1/auth/me", headers=auth_header("VIEWER"))
    db_session.add(UserSectorPermission(
        userId=viewer.json()["id"], sectorId=contract.sectorId, canView=True, canEdit=False,
    ))
    await db_session.commit()
    forbidden = await client.patch(
        f"{URL}/{contract_id}", json={"regularizationStage": "em_tratativa"}, headers=auth_header("VIEWER"),
    )
    assert forbidden.status_code == 403
    await _start(client, auth_header, contract_id)
    visible = await client.get(f"{URL}/{contract_id}", headers=auth_header("VIEWER"))
    assert visible.json()["regularizationStage"] == "aguardando_analise"
    assert visible.json()["canEdit"] is False

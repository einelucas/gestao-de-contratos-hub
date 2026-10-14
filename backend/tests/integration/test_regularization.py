"""Regularização integrada à API, resumo e Kanban existente."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models.contracts import Contract, Sector, Supplier
from app.modules.contracts.rules import contracts_today


async def _seed(db_session, *, days: int = -10) -> str:
    sector = Sector(slug="regularizacao", name="Projetos", acronym="PRO")
    supplier = Supplier(name="Fornecedor Regularização")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    contract = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="REG-100",
        endDate=contracts_today() + timedelta(days=days),
        unit="Dourados",
    )
    db_session.add(contract)
    await db_session.commit()
    return contract.id


async def _start(client, auth_header, contract_id):
    response = await client.patch(
        f"/api/v1/contratos/{contract_id}",
        json={"regularizationStage": "aguardando_analise", "regularizationResponsible": "Samuel"},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_tracking_preserves_actual_expiry_and_dashboard_totals(client, auth_header, db_session):
    contract_id = await _seed(db_session)
    item = await _start(client, auth_header, contract_id)
    assert item["alert"] == "Regularizacao"
    assert item["situation"] == "Vencido"
    assert item["auditStage"] == "AGUARDANDO_ANALISE"
    assert len(item["regularizationHistory"]) == 1
    response = await client.get("/api/v1/contratos/resumo", headers=auth_header("ADMIN"))
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["kpis"]["regularization"] == 1
    assert report["kpis"]["vencido"] == 0
    assert report["kpis"]["onTime"] == 0
    assert report["kpis"]["onTimeBase"] == 1
    assert sum(bucket["count"] for bucket in report["deadlines"]) == 1
    history = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN"))
    assert history.status_code == 200, history.text
    assert history.json()["items"][-1]["remaining"] == 1


async def test_stage_changes_append_history_and_noop_does_not(client, auth_header, db_session):
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    for _ in range(2):
        response = await client.patch(
            f"/api/v1/contratos/{contract_id}",
            json={"regularizationStage": "chamados_elos", "regularizationNotes": "Chamado aberto"},
            headers=auth_header("ADMIN"),
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["regularizationHistory"]) == 2


async def test_cannot_complete_overdue_without_renewal(client, auth_header, db_session):
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    response = await client.patch(
        f"/api/v1/contratos/{contract_id}", json={"regularizationStage": None},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 422, response.text
    saved = await client.get(f"/api/v1/contratos/{contract_id}", headers=auth_header("ADMIN"))
    assert saved.json()["regularizationStage"] == "aguardando_analise"
    assert len(saved.json()["regularizationHistory"]) == 1


@pytest.mark.parametrize("via_audit", [False, True])
async def test_finalization_clears_tracking_without_resurrection(
    client, auth_header, db_session, via_audit
):
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    url = f"/api/v1/contratos/{contract_id}"
    response = await client.patch(
        url + ("/auditoria" if via_audit else ""),
        json={"stage": "FINALIZADO"} if via_audit else {"finalized": True},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["alert"] == "Finalizado"
    assert item["regularizationStage"] is None
    assert item["regularizationHistory"][-1]["stage"] is None


async def test_renewal_clears_both_boards_and_records_completion(client, auth_header, db_session):
    contract_id = await _seed(db_session)
    await _start(client, auth_header, contract_id)
    response = await client.patch(
        f"/api/v1/contratos/{contract_id}",
        json={"endDate": (contracts_today() + timedelta(days=120)).isoformat()},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["alert"] == "Regular"
    assert response.json()["regularizationStage"] is None
    assert response.json()["auditStage"] is None
    assert response.json()["regularizationHistory"][-1]["stage"] is None


async def test_invalid_stage_and_viewer_cannot_mutate_tracking(client, auth_header, db_session):
    contract_id = await _seed(db_session)
    invalid = await client.patch(
        f"/api/v1/contratos/{contract_id}", json={"regularizationStage": "invalida"},
        headers=auth_header("ADMIN"),
    )
    forbidden = await client.patch(
        f"/api/v1/contratos/{contract_id}", json={"regularizationStage": "em_tratativa"},
        headers=auth_header("VIEWER"),
    )
    assert invalid.status_code == 422
    assert forbidden.status_code == 403

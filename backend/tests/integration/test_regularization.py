"""Regularização persistida via API, sem mascarar a vigência real."""

import asyncio
from datetime import timedelta

from app.modules.contracts.rules import contracts_today
from tests.integration.test_contract_update import URL, _seed


async def test_regularization_lifecycle_and_summary(client, auth_header, db_session):
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    headers = auth_header("ADMIN")
    overdue = (contracts_today() - timedelta(days=10)).isoformat()
    started = await client.patch(
        url,
        headers=headers,
        json={
            "endDate": overdue,
            "regularizationStage": "aguardando_analise",
            "regularizationResponsible": "Samuel",
            "regularizationDeadline": contracts_today().isoformat(),
            "regularizationNotes": "Solicitar renovação",
        },
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["alert"] == "Regularizacao"
    assert body["situation"] == "Vencido"
    assert body["auditStage"] == "AGUARDANDO_ANALISE"
    assert len(body["regularizationHistory"]) == 1
    assert (await client.get(url, headers=headers)).json() == body

    report = (await client.get(f"{URL}/resumo", headers=headers)).json()
    assert report["kpis"]["regularization"] == 1
    assert report["kpis"]["vencido"] == 0
    assert report["kpis"]["onTime"] == 0
    assert report["kpis"]["onTimeBase"] == 1
    assert sum(bucket["count"] for bucket in report["deadlines"]) == 1

    denied = await client.patch(
        url,
        headers=auth_header("VIEWER"),
        json={
            "regularizationStage": "em_tratativa",
        },
    )
    assert denied.status_code in (403, 404)
    invalid = await client.patch(url, headers=headers, json={"regularizationStage": "invalida"})
    assert invalid.status_code == 422
    incomplete = await client.patch(url, headers=headers, json={"regularizationStage": None})
    assert incomplete.status_code == 422
    assert (await client.get(url, headers=headers)).json() == body

    renewed = await client.patch(
        url,
        headers=headers,
        json={
            "regularizationStage": None,
            "endDate": (contracts_today() + timedelta(days=90)).isoformat(),
        },
    )
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["alert"] == "Regular"
    assert renewed.json()["auditStage"] is None
    assert len(renewed.json()["regularizationHistory"]) == 2
    assert renewed.json()["regularizationHistory"][-1]["stage"] is None


async def test_concurrent_movements_preserve_history(client, auth_header, db_session):
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    headers = auth_header("ADMIN")
    responses = await asyncio.gather(
        *[
            client.patch(url, headers=headers, json={"regularizationStage": stage})
            for stage in ("chamados_elos", "em_tratativa")
        ]
    )
    assert all(response.status_code == 200 for response in responses)
    body = (await client.get(url, headers=headers)).json()
    history = body["regularizationHistory"]
    assert len(history) == 2
    assert {event["stage"] for event in history} == {"chamados_elos", "em_tratativa"}
    assert history[1]["previousStage"] == history[0]["stage"]


async def test_finalized_contract_cannot_start_regularization(client, auth_header, db_session):
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    headers = auth_header("ADMIN")
    assert (await client.patch(url, headers=headers, json={"finalized": True})).status_code == 200
    response = await client.patch(url, headers=headers, json={"regularizationStage": "em_tratativa"})
    assert response.status_code == 422
    body = (await client.get(url, headers=headers)).json()
    assert body["finalized"] is True
    assert body["regularizationStage"] is None
    assert body["regularizationHistory"] == []


async def test_audit_finalization_closes_regularization(client, auth_header, db_session):
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    headers = auth_header("ADMIN")
    started = await client.patch(
        url,
        headers=headers,
        json={
            "endDate": (contracts_today() - timedelta(days=10)).isoformat(),
            "regularizationStage": "em_tratativa",
        },
    )
    assert started.status_code == 200
    response = await client.patch(f"{url}/auditoria", headers=headers, json={"stage": "FINALIZADO"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["finalized"] is True
    assert body["regularizationStage"] is None
    assert len(body["regularizationHistory"]) == 2
    assert body["regularizationHistory"][-1]["stage"] is None

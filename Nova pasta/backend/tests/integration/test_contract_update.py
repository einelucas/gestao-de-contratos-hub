"""PATCH /contratos/{id}: a resposta HTTP precisa sair certa, não só o banco.

Regressão do "Erro interno ao processar a requisição" ao salvar um contrato:
`update_contract` fazia `commit()` + `session.expire_all()` e depois lia
`item.id`, o que dispara um refresh implícito fora do contexto async
(`sqlalchemy.exc.MissingGreenlet`) — o dado era gravado, mas a API devolvia 500.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.models.contracts import (
    Contract,
    NotificationTeam,
    NotificationTeamMember,
    Sector,
    Supplier,
)

URL = "/api/v1/contratos"


async def _seed(db_session) -> dict[str, str]:
    obras = Sector(slug="obras", name="Obras", acronym="OBR")
    ti = Sector(slug="ti", name="TI", acronym="TI")
    supplier = Supplier(name="Fornecedor X")
    db_session.add_all([obras, ti, supplier])
    await db_session.flush()
    team_obras = NotificationTeam(
        name="Equipe Obras",
        sectorId=obras.id,
        members=[NotificationTeamMember(email="ana@empresa.com", name="Ana")],
    )
    team_obras_2 = NotificationTeam(
        name="Equipe Obras 2",
        sectorId=obras.id,
        members=[NotificationTeamMember(email="bia@empresa.com", name="Bia")],
    )
    team_ti = NotificationTeam(
        name="Equipe TI", sectorId=ti.id, members=[NotificationTeamMember(email="caio@empresa.com")]
    )
    contract = Contract(
        sectorId=obras.id,
        supplierId=supplier.id,
        contractNumber="100",
        startDate=date(2025, 1, 1),
        endDate=date(2030, 1, 1),
        serviceValue=1000,
        ownMaterialValue=0,
        thirdPartyMaterialValue=0,
        totalValue=1000,
        unit="Matriz",
    )
    db_session.add_all([team_obras, team_obras_2, team_ti, contract])
    await db_session.commit()
    return {
        "obras": obras.id,
        "ti": ti.id,
        "team_obras": team_obras.id,
        "team_obras_2": team_obras_2.id,
        "team_ti": team_ti.id,
        "contract": contract.id,
    }


def _as_float(value: Any) -> float:
    return float(value)


# (descrição, payload(ids) -> body, verificação(ids, json))
SCENARIOS: list[tuple[str, Any, Any]] = [
    (
        "fornecedor",
        lambda ids: {"supplier": "Fornecedor Novo"},
        lambda ids, j: j["supplier"] == "Fornecedor Novo",
    ),
    (
        "vigencia",
        lambda ids: {"startDate": "2026-02-01", "endDate": "2031-03-31"},
        lambda ids, j: j["startDate"] == "2026-02-01" and j["endDate"] == "2031-03-31",
    ),
    (
        "valores",
        lambda ids: {
            "serviceValue": "1500.50",
            "ownMaterialValue": "200",
            "thirdPartyMaterialValue": "99.50",
        },
        lambda ids, j: _as_float(j["serviceValue"]) == 1500.5 and _as_float(j["totalValue"]) == 1800.0,
    ),
    ("setor", lambda ids: {"sectorId": ids["ti"]}, lambda ids, j: j["sectorId"] == ids["ti"]),
    ("finalizado", lambda ids: {"finalized": True}, lambda ids, j: j["finalized"] is True),
    (
        "alertas_ativados",
        lambda ids: {"notify": True, "notificationTeamId": ids["team_obras"]},
        lambda ids, j: j["notify"] is True and j["notificationTeamId"] == ids["team_obras"],
    ),
    (
        "equipe",
        lambda ids: {"notificationTeamId": ids["team_obras_2"]},
        lambda ids, j: j["notificationTeamId"] == ids["team_obras_2"]
        and j["notificationTeamName"] == "Equipe Obras 2",
    ),
    ("criticidade", lambda ids: {"criticality": "ALTA"}, lambda ids, j: j["criticality"] == "ALTA"),
    (
        "renovacao_automatica",
        lambda ids: {"autoRenewal": True},
        lambda ids, j: j["autoRenewal"] is True,
    ),
]


@pytest.mark.parametrize(("name", "payload", "check"), SCENARIOS, ids=[s[0] for s in SCENARIOS])
async def test_patch_contract_returns_200_and_persists(
    client, auth_header, db_session, caplog, name, payload, check
) -> None:
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"

    response = await client.patch(url, json=payload(ids), headers=auth_header("ADMIN"))

    assert response.status_code == 200, response.text
    assert "Erro interno" not in response.text
    assert check(ids, response.json())
    assert "MissingGreenlet" not in caplog.text
    assert "greenlet_spawn" not in caplog.text

    # GET posterior (outra sessão/requisição) devolve o mesmo dado persistido.
    again = await client.get(url, headers=auth_header("ADMIN"))
    assert again.status_code == 200
    assert check(ids, again.json())
    assert again.json() == response.json()


async def test_disable_alerts_after_enabling(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    on = await client.patch(
        url,
        json={"notify": True, "notificationTeamId": ids["team_obras"]},
        headers=auth_header("ADMIN"),
    )
    assert on.status_code == 200
    off = await client.patch(url, json={"notify": False}, headers=auth_header("ADMIN"))
    assert off.status_code == 200
    assert off.json()["notify"] is False
    assert (await client.get(url, headers=auth_header("ADMIN"))).json()["notify"] is False


async def test_finalize_and_reopen(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    closed = await client.patch(url, json={"finalized": True}, headers=auth_header("ADMIN"))
    assert closed.status_code == 200
    assert closed.json()["situation"] == "Finalizado"
    reopened = await client.patch(url, json={"finalized": False}, headers=auth_header("ADMIN"))
    assert reopened.status_code == 200
    assert reopened.json()["finalized"] is False
    assert reopened.json()["situation"] != "Finalizado"


async def test_patch_without_changes_returns_200(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    before = (await client.get(url, headers=auth_header("ADMIN"))).json()
    response = await client.patch(url, json={}, headers=auth_header("ADMIN"))
    assert response.status_code == 200
    assert response.json()["contractNumber"] == before["contractNumber"]
    assert response.json()["supplier"] == before["supplier"]


async def test_multiple_fields_in_one_save(client, auth_header, db_session) -> None:
    """Simula o formulário: várias alterações num único "Salvar alterações"."""
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    body = {
        "supplier": "Outro Fornecedor",
        "endDate": "2032-12-31",
        "serviceValue": "2000",
        "notify": True,
        "notificationTeamId": ids["team_obras"],
        "criticality": "MEDIA",
        "autoRenewal": True,
    }
    response = await client.patch(url, json=body, headers=auth_header("ADMIN"))
    assert response.status_code == 200, response.text
    data = (await client.get(url, headers=auth_header("ADMIN"))).json()
    assert data["supplier"] == "Outro Fornecedor"
    assert data["endDate"] == "2032-12-31"
    assert _as_float(data["totalValue"]) == 2000.0
    assert data["notificationTeamName"] == "Equipe Obras"
    assert data["criticality"] == "MEDIA"
    assert data["autoRenewal"] is True


async def test_create_contract_returns_201_or_200_with_body(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    response = await client.post(
        URL,
        json={"sectorId": ids["obras"], "supplier": "Fornecedor Y", "contractNumber": "300"},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code in (200, 201), response.text
    created = response.json()
    assert created["contractNumber"] == "300"
    fetched = await client.get(f"{URL}/{created['id']}", headers=auth_header("ADMIN"))
    assert fetched.status_code == 200
    assert fetched.json()["supplier"] == "Fornecedor Y"


async def test_sector_change_conflicts_with_same_number(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    created = await client.post(
        URL,
        json={"sectorId": ids["ti"], "supplier": "Y", "contractNumber": "100"},
        headers=auth_header("ADMIN"),
    )
    assert created.status_code in (200, 201)
    response = await client.patch(
        f"{URL}/{ids['contract']}", json={"sectorId": ids["ti"]}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 409
    # Nada foi alterado.
    still = (await client.get(f"{URL}/{ids['contract']}", headers=auth_header("ADMIN"))).json()
    assert still["sectorId"] == ids["obras"]


async def test_team_from_other_sector_is_rejected(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    url = f"{URL}/{ids['contract']}"
    response = await client.patch(
        url, json={"notificationTeamId": ids["team_ti"]}, headers=auth_header("ADMIN")
    )
    assert 400 <= response.status_code < 500
    assert response.status_code != 500
    still = (await client.get(url, headers=auth_header("ADMIN"))).json()
    assert still["notificationTeamId"] is None

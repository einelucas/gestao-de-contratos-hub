"""Histórico real (não projetado) de `GET /contratos/vencidos-historico`."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.models.contracts import Contract, OverdueContractTracking, Sector, Supplier
from app.modules.contracts.rules import contracts_today


async def _seed(db_session, *, overdue: int, regular: int = 0) -> dict[str, list[str]]:
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor X")
    db_session.add_all([sector, supplier])
    await db_session.flush()

    today = contracts_today()
    overdue_contracts = [
        Contract(
            sectorId=sector.id,
            supplierId=supplier.id,
            contractNumber=f"V{index}",
            endDate=today - timedelta(days=5),
        )
        for index in range(overdue)
    ]
    regular_contracts = [
        Contract(
            sectorId=sector.id,
            supplierId=supplier.id,
            contractNumber=f"R{index}",
            endDate=today + timedelta(days=100),
        )
        for index in range(regular)
    ]
    db_session.add_all(overdue_contracts + regular_contracts)
    # Commit antes de ler `.id`: o default (uuid4) só é aplicado no flush.
    await db_session.commit()
    return {
        "overdue": [contract.id for contract in overdue_contracts],
        "regular": [contract.id for contract in regular_contracts],
    }


async def test_first_call_starts_history_from_today_with_zero_resolved(
    client, auth_header, db_session
) -> None:
    await _seed(db_session, overdue=3)

    response = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("VIEWER"))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["remaining"] == 3
    assert items[0]["resolved"] == 0
    assert items[0]["date"] == contracts_today().isoformat()


async def test_resolving_a_contract_increments_cumulative_and_never_decreases(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session, overdue=2)

    first = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("VIEWER"))
    assert first.json()["items"][-1] == {
        "date": contracts_today().isoformat(),
        "remaining": 2,
        "resolved": 0,
    }

    # Um dos contratos vencidos é finalizado (deixou de estar "Vencido").
    contract = await db_session.get(Contract, ids["overdue"][0])
    contract.finalized = True
    await db_session.commit()

    second = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("VIEWER"))
    items = second.json()["items"]
    # Mesma chamada no mesmo dia atualiza o ponto em vez de duplicar.
    assert len(items) == 1
    assert items[-1]["remaining"] == 1
    assert items[-1]["resolved"] == 1

    # Confirma a baixa real no banco (não é só o retrato do dia).
    rows = (await db_session.execute(select(OverdueContractTracking))).scalars().all()
    resolved_rows = [row for row in rows if row.resolvedAt is not None]
    assert len(resolved_rows) == 1
    assert resolved_rows[0].contractId == ids["overdue"][0]


async def test_history_is_org_wide_regardless_of_sector_permission(client, auth_header, db_session) -> None:
    """VIEWER sem nenhuma permissão de setor ainda vê o indicador agregado."""
    await _seed(db_session, overdue=1)

    listed = await client.get("/api/v1/contratos", headers=auth_header("VIEWER"))
    assert listed.json()["total"] == 0  # sem permissão de setor: não vê contratos individuais

    history = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("VIEWER"))
    assert history.status_code == 200
    assert history.json()["items"][-1]["remaining"] == 1


async def test_new_overdue_contract_does_not_reduce_resolved_count(client, auth_header, db_session) -> None:
    ids = await _seed(db_session, overdue=1, regular=1)

    first = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN"))
    assert first.json()["items"][-1] == {"date": contracts_today().isoformat(), "remaining": 1, "resolved": 0}

    # O contrato que ainda não vencia agora vence (entra como "restante", não mexe no resolvido).
    contract = await db_session.get(Contract, ids["regular"][0])
    contract.endDate = date.today() - timedelta(days=1)
    await db_session.commit()

    second = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN"))
    assert second.json()["items"][-1]["remaining"] == 2
    assert second.json()["items"][-1]["resolved"] == 0

"""Histórico real (não projetado) de `GET /contratos/vencidos-historico`."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.contracts import (
    Contract,
    OverdueContractTracking,
    OverdueDailySnapshot,
    Sector,
    Supplier,
)
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
    assert first.json()["items"][-1] == {
        "date": contracts_today().isoformat(),
        "remaining": 1,
        "resolved": 0,
    }

    # O contrato que ainda não vencia agora vence (entra como "restante", não mexe no resolvido).
    contract = await db_session.get(Contract, ids["regular"][0])
    contract.endDate = date.today() - timedelta(days=1)
    await db_session.commit()

    second = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN"))
    assert second.json()["items"][-1]["remaining"] == 2
    assert second.json()["items"][-1]["resolved"] == 0


HISTORY_URL = "/api/v1/contratos/vencidos-historico"


async def _open_tracking_counts(db_session) -> dict[str, int]:
    rows = await db_session.execute(
        select(OverdueContractTracking.contractId, func.count())
        .where(OverdueContractTracking.resolvedAt.is_(None))
        .group_by(OverdueContractTracking.contractId)
    )
    return {contract_id: count for contract_id, count in rows.all()}


async def test_concurrent_calls_do_not_fail_or_duplicate(client, auth_header, db_session) -> None:
    """Várias abas abrindo o Dashboard ao mesmo tempo: nada de 500 nem linhas duplicadas."""
    ids = await _seed(db_session, overdue=3, regular=1)

    responses = await asyncio.gather(
        *(client.get(HISTORY_URL, headers=auth_header("ADMIN")) for _ in range(6))
    )
    assert [r.status_code for r in responses] == [200] * 6
    for response in responses:
        assert response.json()["items"][-1]["remaining"] == 3
        assert response.json()["items"][-1]["resolved"] == 0

    counts = await _open_tracking_counts(db_session)
    assert counts == {contract_id: 1 for contract_id in ids["overdue"]}
    snapshots = (
        await db_session.execute(select(func.count()).select_from(OverdueDailySnapshot))
    ).scalar_one()
    assert snapshots == 1


async def test_concurrent_calls_after_resolution_do_not_inflate_resolved(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session, overdue=2)
    assert (await client.get(HISTORY_URL, headers=auth_header("ADMIN"))).status_code == 200

    contract = await db_session.get(Contract, ids["overdue"][0])
    contract.finalized = True
    await db_session.commit()

    responses = await asyncio.gather(
        *(client.get(HISTORY_URL, headers=auth_header("ADMIN")) for _ in range(6))
    )
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()["items"][-1]["resolved"] == 1 for r in responses)
    resolved_rows = (
        await db_session.execute(
            select(func.count())
            .select_from(OverdueContractTracking)
            .where(OverdueContractTracking.resolvedAt.is_not(None))
        )
    ).scalar_one()
    assert resolved_rows == 1


async def test_repeated_calls_are_idempotent(client, auth_header, db_session) -> None:
    await _seed(db_session, overdue=2, regular=2)
    first = await client.get(HISTORY_URL, headers=auth_header("ADMIN"))
    for _ in range(3):
        again = await client.get(HISTORY_URL, headers=auth_header("ADMIN"))
        assert again.status_code == 200
        assert again.json() == first.json()
    rows = (await db_session.execute(select(func.count()).select_from(OverdueContractTracking))).scalar_one()
    assert rows == 2


async def test_contract_overdue_again_opens_new_cycle(client, auth_header, db_session) -> None:
    """Vence, é regularizado, vence de novo: um ciclo resolvido + um novo em aberto."""
    ids = await _seed(db_session, overdue=1)
    contract_id = ids["overdue"][0]
    await client.get(HISTORY_URL, headers=auth_header("ADMIN"))

    contract = await db_session.get(Contract, contract_id)
    contract.endDate = contracts_today() + timedelta(days=200)
    await db_session.commit()
    resolved = await client.get(HISTORY_URL, headers=auth_header("ADMIN"))
    assert resolved.json()["items"][-1] == {
        "date": contracts_today().isoformat(),
        "remaining": 0,
        "resolved": 1,
    }

    contract.endDate = contracts_today() - timedelta(days=1)
    await db_session.commit()
    overdue_again = await client.get(HISTORY_URL, headers=auth_header("ADMIN"))
    assert overdue_again.json()["items"][-1]["remaining"] == 1
    # O acumulado conta regularizações (ciclos), nunca diminui.
    assert overdue_again.json()["items"][-1]["resolved"] == 1
    assert await _open_tracking_counts(db_session) == {contract_id: 1}


async def test_database_rejects_second_open_cycle(db_session) -> None:
    """O índice parcial (migração 0007) é a última linha de defesa contra duplicidade."""
    ids = await _seed(db_session, overdue=1)
    contract_id = ids["overdue"][0]
    today = contracts_today()
    db_session.add(OverdueContractTracking(contractId=contract_id, firstSeenOverdueAt=today))
    await db_session.commit()
    db_session.add(OverdueContractTracking(contractId=contract_id, firstSeenOverdueAt=today))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    # Ciclos já resolvidos não contam para a restrição.
    db_session.add(
        OverdueContractTracking(contractId=contract_id, firstSeenOverdueAt=today, resolvedAt=today)
    )
    await db_session.commit()

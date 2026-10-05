"""Histórico real de regularização dos contratos vencidos.

Alimenta o gráfico "Evolução da Regularização dos Contratos Vencidos" do
Dashboard. Diferente do resumo (`summary.py`), este indicador é org-wide —
igual para qualquer usuário com acesso ao Hub, independente de
UserSectorPermission — porque o que é exposto são só contagens agregadas
(quantos vencidos, quantos regularizados), nunca contratos individuais.

Reconciliação sob demanda: a cada chamada, compara a lista real de contratos
vencidos agora com os ciclos em aberto gravados da última vez. Quem saiu da
lista virou "regularizado" (contador acumulado, nunca diminui); quem é novo
só abre um ciclo. Não há job nem projeção — cada ponto do histórico é o
retrato real do dia em que foi gravado.

Concorrência: o GET grava no banco, então duas abas/usuários podem reconciliar
ao mesmo tempo. A reconciliação inteira roda sob um advisory lock de transação
(serializa quem chega junto) e o banco reforça os invariantes: snapshot único
por data (upsert) e no máximo um ciclo em aberto por contrato (índice parcial,
migração 0007).
"""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import utcnow
from app.models.contracts import Contract, OverdueContractTracking, OverdueDailySnapshot
from app.modules.contracts.rules import contracts_today, derive_alert, derive_situation
from app.modules.contracts.schemas import OverdueHistoryOut, OverdueHistoryPointOut


async def _current_overdue_contract_ids(session: AsyncSession) -> set[str]:
    rows = (await session.execute(select(Contract.id, Contract.finalized, Contract.endDate))).all()
    today = contracts_today()
    overdue: set[str] = set()
    for contract_id, finalized, end_date in rows:
        situation = derive_situation(finalized=finalized, end_date=end_date, today=today)
        if derive_alert(situation=situation, end_date=end_date, today=today) == "Vencido":
            overdue.add(contract_id)
    return overdue


# Chave arbitrária e fixa do advisory lock da reconciliação (só precisa ser única no app).
_RECONCILE_LOCK_KEY = 0x0D0E_4157


async def reconcile_and_get_history(session: AsyncSession) -> OverdueHistoryOut:
    # Liberado automaticamente no commit/rollback; a segunda requisição espera e,
    # ao entrar, já enxerga o que a primeira gravou (reconciliação idempotente).
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _RECONCILE_LOCK_KEY})
    today = contracts_today()
    overdue_ids = await _current_overdue_contract_ids(session)

    active_rows = (
        (
            await session.execute(
                select(OverdueContractTracking).where(OverdueContractTracking.resolvedAt.is_(None))
            )
        )
        .scalars()
        .all()
    )
    active_by_contract = {row.contractId: row for row in active_rows}

    for contract_id, row in active_by_contract.items():
        if contract_id not in overdue_ids:
            row.resolvedAt = today

    new_ids = overdue_ids - active_by_contract.keys()
    for contract_id in new_ids:
        session.add(OverdueContractTracking(contractId=contract_id, firstSeenOverdueAt=today))

    await session.flush()

    resolved_cumulative = (
        await session.execute(
            select(func.count())
            .select_from(OverdueContractTracking)
            .where(OverdueContractTracking.resolvedAt.is_not(None))
        )
    ).scalar_one()

    upsert = insert(OverdueDailySnapshot).values(
        date=today, remaining=len(overdue_ids), resolvedCumulative=resolved_cumulative
    )
    await session.execute(
        upsert.on_conflict_do_update(
            index_elements=[OverdueDailySnapshot.date],
            set_={
                "remaining": upsert.excluded.remaining,
                "resolvedCumulative": upsert.excluded.resolvedCumulative,
                "updatedAt": utcnow(),
            },
        )
    )

    await session.commit()

    history = (
        (await session.execute(select(OverdueDailySnapshot).order_by(OverdueDailySnapshot.date.asc())))
        .scalars()
        .all()
    )
    return OverdueHistoryOut(
        items=[
            OverdueHistoryPointOut(
                date=point.date, remaining=point.remaining, resolved=point.resolvedCumulative
            )
            for point in history
        ]
    )

"""Resumo do dashboard de contratos (`GET /contratos/resumo`).

Tudo é calculado sobre a mesma lista que o usuário vê em /contratos (já
filtrada por UserSectorPermission), com o mesmo "hoje" (America/Sao_Paulo) e as
mesmas regras de status (ATTENTION_DAYS = 20). Filtros:

- `sectorId` / `unit`: recortam a base.
- `de` / `ate`: período do FIM DE VIGÊNCIA — com período, contratos sem data
  ficam de fora; sem período, a série mensal cobre 5 meses atrás a 6 à frente.

"Em dia" usa a vigência real dos contratos ativos com data. Iniciar uma
regularização não renova a vigência nem altera o histórico de vencimentos.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.modules.contracts import service
from app.modules.contracts.rules import (
    REGULARIZATION_AUDIT_STAGES,
    contracts_today,
    derive_alert,
)
from app.modules.contracts.schemas import (
    ContractOut,
    ContractSummaryOut,
    DeadlineBucketOut,
    OverdueStatsOut,
    StatusCountOut,
    SummaryGroupOut,
    SummaryKpisOut,
    SummaryMonthOut,
    SummaryValuesOut,
)

STATUS_ORDER = ("Regular", "Atencao", "Vencido", "Regularizacao", "Finalizado", "SemData")
STATUS_LABEL = {
    "Regular": "Regulares",
    "Atencao": "Atenção",
    "Vencido": "Vencidos pendentes",
    "Regularizacao": "Em regularização",
    "Finalizado": "Finalizados",
    "SemData": "Sem data",
}
_MONTH_ABBR = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

# (chave, rótulo, teste sobre dias para vencer) — faixas exclusivas, só contratos não finalizados.
_DEADLINE_BUCKETS: tuple[tuple[str, str, Callable[[int], bool]], ...] = (
    ("overdue", "Vencidos", lambda d: d < 0),
    ("today", "Vencem hoje", lambda d: d == 0),
    ("next7", "Em 1 a 7 dias", lambda d: 1 <= d <= 7),
    ("next30", "Em 8 a 30 dias", lambda d: 8 <= d <= 30),
    ("next60", "Em 31 a 60 dias", lambda d: 31 <= d <= 60),
    ("next90", "Em 61 a 90 dias", lambda d: 61 <= d <= 90),
    ("later", "Após 90 dias", lambda d: d > 90),
)


def _money(items: list[ContractOut]) -> float:
    return float(sum((Decimal(item.total_value) for item in items), Decimal("0")))


def _percent(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _is_regularization(item: ContractOut) -> bool:
    """Conta o contrato como "Em regularização" no Dashboard.

    É aditivo/sobreposto: um contrato em etapa de Auditoria (de "Aguardando
    Análise" até "Em Tratativa") entra em "Em regularização" sem deixar de ser
    "Vencido"/"Atenção" no restante do app nem nas demais contagens do resumo —
    quem acompanha vencimentos continua vendo o mesmo número de vencidos.
    """
    return item.alert == "Regularizacao" or (
        not item.finalized and item.audit_stage in REGULARIZATION_AUDIT_STAGES
    )


def _status(item: ContractOut) -> str:
    """Status exclusivo do contrato na dimensão de status do Dashboard.

    Ignora a sobreposição de regularização: um contrato vencido que também está
    em regularização continua com status "Vencido" aqui. Assim os status somam
    o total de contratos e "Em regularização" é apresentado à parte.
    """
    return derive_alert(situation=item.situation, end_date=item.end_date)


def _group(items: list[ContractOut], key: Callable[[ContractOut], str]) -> list[SummaryGroupOut]:
    buckets: dict[str, list[ContractOut]] = defaultdict(list)
    for item in items:
        buckets[key(item)].append(item)
    groups = []
    for label, members in buckets.items():
        counts = {status: sum(1 for m in members if _status(m) == status) for status in STATUS_ORDER}
        groups.append(
            SummaryGroupOut(
                key=label,
                label=label or "Sem unidade",
                total=len(members),
                regular=counts["Regular"],
                regularization=sum(1 for m in members if _is_regularization(m)),
                atencao=counts["Atencao"],
                vencido=counts["Vencido"],
                finalizado=counts["Finalizado"],
                sem_data=counts["SemData"],
                total_value=_money(members),
            )
        )
    return sorted(groups, key=lambda g: (-g.total, g.label))


async def build_summary(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    sector_id: str | None = None,
    unit: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ContractSummaryOut:
    today = contracts_today()
    items = await service.list_contracts(session, actor, sector_id=sector_id)
    if unit:
        items = [item for item in items if item.unit == unit]
    if date_from or date_to:
        items = [
            item
            for item in items
            if item.end_date is not None
            and (date_from is None or item.end_date >= date_from)
            and (date_to is None or item.end_date <= date_to)
        ]

    total = len(items)
    counts = {status: sum(1 for item in items if _status(item) == status) for status in STATUS_ORDER}
    regularization_items = [item for item in items if _is_regularization(item)]
    regularization_count = len(regularization_items)
    on_time = sum(
        1
        for item in items
        if not item.finalized
        and item.end_date is not None
        and item.end_date >= today
    )
    on_time_base = sum(
        1
        for item in items
        if not item.finalized and item.end_date is not None
    )

    by_status = [
        StatusCountOut(
            key=status,
            label=STATUS_LABEL[status],
            count=counts[status],
            percent=_percent(counts[status], total),
            total_value=_money([item for item in items if _status(item) == status]),
        )
        for status in STATUS_ORDER
    ]

    # "Em regularização" é uma dimensão transversal: mostramos o total e a
    # composição pelos status exclusivos, sem somá-la ao total de contratos.
    regularization_by_status = [
        StatusCountOut(
            key=status,
            label=STATUS_LABEL[status],
            count=sum(1 for item in regularization_items if _status(item) == status),
            percent=_percent(
                sum(1 for item in regularization_items if _status(item) == status),
                regularization_count,
            ),
            total_value=_money(
                [item for item in regularization_items if _status(item) == status]
            ),
        )
        for status in STATUS_ORDER
        if any(_status(item) == status for item in regularization_items)
    ]

    # Série mensal pelo fim de vigência.
    start = _month_start(date_from) if date_from else _add_months(_month_start(today), -5)
    end = _month_start(date_to) if date_to else _add_months(_month_start(today), 6)
    months: list[SummaryMonthOut] = []
    cursor = start
    while cursor <= end and len(months) < 60:
        in_month = [
            item
            for item in items
            if item.end_date is not None and _month_start(item.end_date) == cursor
        ]
        active = [item for item in in_month if not item.finalized]
        # A série mensal também é exclusiva: "Em regularização" é uma dimensão
        # transversal e não entra empilhada aqui (evita contar o mesmo contrato
        # como vencido e em regularização ao mesmo tempo).
        overdue_count = sum(1 for item in active if _status(item) == "Vencido")
        upcoming_count = sum(1 for item in active if _status(item) in ("Regular", "Atencao"))
        months.append(
            SummaryMonthOut(
                month=cursor.strftime("%Y-%m"),
                label=f"{_MONTH_ABBR[cursor.month - 1]}/{cursor.strftime('%y')}",
                expiring=len(active),
                upcoming=upcoming_count,
                overdue=overdue_count,
                regularization=0,
                finalized=len(in_month) - len(active),
                total_value=_money(active),
            )
        )
        cursor = _add_months(cursor, 1)

    open_items = [item for item in items if not item.finalized]
    deadlines = [
        DeadlineBucketOut(
            key=key,
            label=label,
            count=sum(
                1
                for item in open_items
                if item.days_to_end is not None and test(item.days_to_end)
            ),
        )
        for key, label, test in _DEADLINE_BUCKETS
    ]
    deadlines.append(
        DeadlineBucketOut(
            key="withoutDate",
            label="Sem data",
            count=sum(1 for item in open_items if item.days_to_end is None),
        )
    )

    overdue_days = [-(item.days_to_end or 0) for item in items if _status(item) == "Vencido"]
    total_value = _money(items)

    return ContractSummaryOut(
        today=today,
        period_start=date_from,
        period_end=date_to,
        sector_id=sector_id,
        unit=unit,
        kpis=SummaryKpisOut(
            regularization_with_date=sum(
                1
                for item in items
                if _is_regularization(item) and item.end_date is not None
            ),
            total=total,
            regular=counts["Regular"],
            regularization=regularization_count,
            atencao=counts["Atencao"],
            vencido=counts["Vencido"],
            finalizado=counts["Finalizado"],
            sem_data=counts["SemData"],
            active=total - counts["Finalizado"],
            on_time=on_time,
            on_time_base=on_time_base,
            on_time_percent=_percent(on_time, on_time_base),
        ),
        by_status=by_status,
        regularization_by_status=regularization_by_status,
        by_sector=_group(items, lambda item: item.sector_name),
        by_unit=_group(items, lambda item: item.unit),
        monthly=months,
        deadlines=deadlines,
        overdue=OverdueStatsOut(
            count=len(overdue_days),
            average_days=round(sum(overdue_days) / len(overdue_days), 1) if overdue_days else 0.0,
            max_days=max(overdue_days, default=0),
        ),
        values=SummaryValuesOut(
            has_values=total_value > 0,
            total=total_value,
            active=_money(open_items),
            overdue=_money([item for item in items if _status(item) == "Vencido"]),
            attention=_money([item for item in items if _status(item) == "Atencao"]),
        ),
    )

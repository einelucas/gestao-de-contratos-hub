"""Régua fixa dos alertas de vencimento (funções puras, sem banco).

Marcos por ciclo de vigência (o ciclo é o fim de vigência atual):

    ANTECEDENCIA 45 dias · ANTECEDENCIA 20 dias · ANTECEDENCIA 1 dia · VENCIMENTO (0)

e, depois de vencido, VENCIDO a cada 7 dias (7, 14, 21…).

Recuperação de marco perdido — cada marco tem uma janela que vai do próprio dia
até a véspera do marco seguinte, sem sobreposição:

    45 → faltam 45…21 dias · 20 → faltam 20…2 · 1 → falta 1 · 0 → vence hoje

Se o job ficou fora do ar no dia do marco, ele é enviado quando o job voltar,
ainda dentro da janela (uma única vez: o motor só envia um marco que ainda não
foi processado). O que separa **indisponibilidade do job** de **ativação
tardia** é a data do marco versus `notifyEnabledOn`: marco cuja data é anterior
ao dia em que os alertas foram ligados não é recuperado — ligar os alertas com
15 dias restantes faz o próximo marco ser o de 1 dia.

VENCIDO mantém a recorrência exata de 7 em 7 dias (sem recuperação).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.models.contracts import NOTICE_DAYS_NOT_APPLICABLE, ContractNotificationType

OVERDUE_REPEAT_DAYS = 7
# Marcos de antecedência em dias, do mais distante ao mais próximo; 0 = dia do vencimento.
ADVANCE_MILESTONES: tuple[int, ...] = (45, 20, 1)
MILESTONES: tuple[int, ...] = (*ADVANCE_MILESTONES, 0)


@dataclass(frozen=True, slots=True)
class AlertDecision:
    type: ContractNotificationType
    # Data que entra na chave de deduplicação: fim de vigência (ANTECEDENCIA/
    # VENCIMENTO) ou o marco semanal endDate + 7·n (VENCIDO).
    reference_date: date
    notice_days: int
    days_to_end: int
    reason: str
    # True quando o marco está sendo enviado depois do seu dia (recuperação).
    recovered: bool = False


def _milestone_window(days: int) -> int | None:
    """Marco cuja janela contém `days` (dias para vencer), ou None."""
    for index, milestone in enumerate(MILESTONES):
        next_milestone = MILESTONES[index + 1] if index + 1 < len(MILESTONES) else None
        lower = next_milestone + 1 if next_milestone is not None else milestone
        if lower <= days <= milestone:
            return milestone
    return None


def evaluate(
    *,
    notify: bool,
    finalized: bool,
    end_date: date | None,
    today: date,
    notify_enabled_on: date | None = None,
) -> AlertDecision | None:
    """Marco aplicável hoje (sem olhar o histórico; o motor descarta marcos já processados)."""
    if not notify or finalized or end_date is None:
        return None

    days = (end_date - today).days

    milestone = _milestone_window(days)
    if milestone is not None:
        milestone_date = end_date - timedelta(days=milestone)
        # Ativação tardia: o marco já tinha passado quando os alertas foram ligados.
        if notify_enabled_on is not None and milestone_date < notify_enabled_on:
            return None
        recovered = days != milestone
        if milestone == 0:
            return AlertDecision(
                type=ContractNotificationType.VENCIMENTO,
                reference_date=end_date,
                notice_days=NOTICE_DAYS_NOT_APPLICABLE,
                days_to_end=0,
                reason="Contrato vence hoje",
            )
        reason = f"Marco de {milestone} dias antes do vencimento"
        if recovered:
            reason += f" (recuperado: faltam {days} dias)"
        return AlertDecision(
            type=ContractNotificationType.ANTECEDENCIA,
            reference_date=end_date,
            notice_days=milestone,
            days_to_end=days,
            reason=reason,
            recovered=recovered,
        )

    overdue = -days
    if overdue > 0 and overdue % OVERDUE_REPEAT_DAYS == 0:
        return AlertDecision(
            type=ContractNotificationType.VENCIDO,
            # Marco determinístico: endDate + 7·n, que é o próprio `today` aqui.
            reference_date=today,
            notice_days=NOTICE_DAYS_NOT_APPLICABLE,
            days_to_end=days,
            reason=f"Contrato vencido há {overdue} dias (alerta a cada {OVERDUE_REPEAT_DAYS} dias)",
        )

    return None


def still_same_cycle(*, notify: bool, finalized: bool, end_date: date | None, cycle_end_date: date) -> bool:
    """Usado no retry: só reenvia se o alerta ainda se refere ao ciclo atual do contrato."""
    return notify and not finalized and end_date == cycle_end_date

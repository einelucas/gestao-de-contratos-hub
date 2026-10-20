"""Regras de entrada, saída e conclusão do Kanban de auditoria."""

from __future__ import annotations

from datetime import date

from app.models.common import utcnow
from app.models.contracts import Contract
from app.modules.contracts.rules import (
    contracts_today,
    derive_alert,
    derive_situation,
    effective_end_date,
    is_effectively_finalized,
)

AWAITING_ANALYSIS = "AGUARDANDO_ANALISE"
FINALIZED = "FINALIZADO"

# Antecedência com que um contrato ainda vigente entra sozinho em "Aguardando
# análise": no dia do vencimento e nos 5 dias anteriores (a data final é
# inclusiva, então `days_to_end == 5` já entra). Contratos vencidos entram
# sempre, como antes.
KANBAN_ENTRY_DAYS = 5


def alert_without_finalization(item: Contract) -> str:
    effective_end = effective_end_date(
        end_date=item.endDate,
        dilation=item.dilation,
        dilation_end_date=item.dilationEndDate,
    )
    situation = derive_situation(
        finalized=False,
        end_date=item.endDate,
        dilation=item.dilation,
        dilation_end_date=item.dilationEndDate,
    )
    return derive_alert(situation=situation, end_date=effective_end)


def kanban_entry_stage(
    *,
    finalized: bool,
    end_date: date | None,
    dilation: bool = False,
    dilation_end_date: date | None = None,
    today: date | None = None,
) -> str | None:
    """Etapa de entrada automática no Kanban, ou `None` quando não se aplica.

    Entram em "Aguardando análise" os contratos não finalizados que já
    venceram ou que vencem em até `KANBAN_ENTRY_DAYS` dias. A vigência
    considerada é a efetiva (dilação manda, quando existir).
    """
    today = today or contracts_today()
    if is_effectively_finalized(
        finalized=finalized,
        dilation=dilation,
        dilation_end_date=dilation_end_date,
        today=today,
    ):
        return None
    effective_end = effective_end_date(
        end_date=end_date,
        dilation=dilation,
        dilation_end_date=dilation_end_date,
    )
    if effective_end is None:
        return None
    if (effective_end - today).days <= KANBAN_ENTRY_DAYS:
        return AWAITING_ANALYSIS
    return None


def sync_contract_audit_stage(item: Contract, *, deadline_changed: bool = False) -> None:
    """Mantém entrada automática de vencidos/quase vencidos sem apagar o fluxo manual.

    A Auditoria passou a aceitar todos os contratos. Por isso uma renovação de
    vigência não pode mais remover silenciosamente uma etapa escolhida pelo time.
    """
    underlying_alert = alert_without_finalization(item)

    if deadline_changed and underlying_alert != "Vencido":
        item.finalized = False
        item.auditStage = None
        item.auditStageEnteredAt = None
        # A nova vigência ainda pode estar na janela de entrada automática.
        _enter_awaiting_analysis_if_due(item)
        return

    if item.auditStage is None:
        _enter_awaiting_analysis_if_due(item)
        return

    if item.auditStageEnteredAt is None:
        item.auditStageEnteredAt = utcnow()

    if is_effectively_finalized(
        finalized=item.finalized,
        dilation=item.dilation,
        dilation_end_date=item.dilationEndDate,
    ):
        if item.auditStage != FINALIZED:
            item.auditStage = FINALIZED
            item.auditStageEnteredAt = utcnow()
    elif item.auditStage == FINALIZED:
        item.auditStage = AWAITING_ANALYSIS
        item.auditStageEnteredAt = utcnow()


def _enter_awaiting_analysis_if_due(item: Contract) -> None:
    if kanban_entry_stage(
        finalized=item.finalized,
        end_date=item.endDate,
        dilation=item.dilation,
        dilation_end_date=item.dilationEndDate,
    ) == AWAITING_ANALYSIS:
        item.auditStage = AWAITING_ANALYSIS
        item.auditStageEnteredAt = utcnow()

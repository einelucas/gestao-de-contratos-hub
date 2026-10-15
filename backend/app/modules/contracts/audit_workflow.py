"""Regras de entrada, saída e conclusão do Kanban de auditoria."""

from __future__ import annotations

from app.models.common import utcnow
from app.models.contracts import Contract
from app.modules.contracts.rules import derive_alert, derive_situation

AWAITING_ANALYSIS = "AGUARDANDO_ANALISE"
FINALIZED = "FINALIZADO"


def alert_without_finalization(item: Contract) -> str:
    situation = derive_situation(finalized=False, end_date=item.endDate)
    return derive_alert(situation=situation, end_date=item.endDate)


def sync_contract_audit_stage(item: Contract, *, deadline_changed: bool = False) -> None:
    """Mantém entrada automática de vencidos sem apagar o fluxo manual.

    A Auditoria passou a aceitar todos os contratos. Por isso uma renovação de
    vigência não pode mais remover silenciosamente uma etapa escolhida pelo time.
    """
    underlying_alert = alert_without_finalization(item)

    if deadline_changed and underlying_alert != "Vencido":
        item.finalized = False
        item.auditStage = None
        item.auditStageEnteredAt = None
        return

    if item.auditStage is None:
        if not item.finalized and underlying_alert == "Vencido":
            item.auditStage = AWAITING_ANALYSIS
            item.auditStageEnteredAt = utcnow()
        return

    if item.auditStageEnteredAt is None:
        item.auditStageEnteredAt = utcnow()

    if item.finalized:
        if item.auditStage != FINALIZED:
            item.auditStage = FINALIZED
            item.auditStageEnteredAt = utcnow()
    elif item.auditStage == FINALIZED:
        item.auditStage = AWAITING_ANALYSIS
        item.auditStageEnteredAt = utcnow()

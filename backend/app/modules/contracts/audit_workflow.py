"""Regras de entrada, saída e conclusão do Kanban de auditoria."""

from __future__ import annotations

from app.models.contracts import Contract
from app.modules.contracts.rules import derive_alert, derive_situation

AWAITING_ANALYSIS = "AGUARDANDO_ANALISE"
FINALIZED = "FINALIZADO"


def alert_without_finalization(item: Contract) -> str:
    situation = derive_situation(finalized=False, end_date=item.endDate)
    return derive_alert(situation=situation, end_date=item.endDate)


def sync_contract_audit_stage(item: Contract, *, deadline_changed: bool = False) -> None:
    """Mantém o Kanban coerente com vigência e finalização do contrato."""
    underlying_alert = alert_without_finalization(item)

    # Alterar manualmente a vigência para uma data não vencida reabre o contrato,
    # devolve seu status calculado (Regular/Atenção/Sem data) e o remove do fluxo.
    if deadline_changed and underlying_alert != "Vencido":
        item.finalized = False
        item.auditStage = None
        return

    if item.auditStage is None:
        if not item.finalized and underlying_alert == "Vencido":
            item.auditStage = AWAITING_ANALYSIS
        return

    if item.finalized:
        item.auditStage = FINALIZED
    elif underlying_alert != "Vencido":
        item.auditStage = None
    elif item.auditStage == FINALIZED:
        item.auditStage = AWAITING_ANALYSIS

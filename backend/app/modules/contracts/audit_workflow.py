"""Regras de entrada, saída e conclusão do Kanban de auditoria."""

from __future__ import annotations

from datetime import date

from app.models.common import utcnow
from app.models.contracts import Contract
from app.modules.contracts.rules import contracts_today, derive_alert, derive_situation

AWAITING_ANALYSIS = "AGUARDANDO_ANALISE"
FINALIZED = "FINALIZADO"

# Antecedência com que um contrato ainda vigente entra sozinho em "Aguardando
# análise": no dia do vencimento e nos 5 dias anteriores (a data final é
# inclusiva, então `days_to_end == 5` já entra). Contratos vencidos entram
# sempre, como antes.
KANBAN_ENTRY_DAYS = 5


def alert_without_finalization(item: Contract) -> str:
    situation = derive_situation(finalized=False, end_date=item.endDate)
    return derive_alert(situation=situation, end_date=item.endDate)


def kanban_entry_stage(
    *,
    finalized: bool,
    end_date: date | None,
    today: date | None = None,
) -> str | None:
    """Etapa de entrada automática no Kanban, ou `None` quando não se aplica.

    Entram em "Aguardando análise" os contratos não finalizados que já
    venceram ou que vencem em até `KANBAN_ENTRY_DAYS` dias.
    """
    today = today or contracts_today()
    if finalized or end_date is None:
        return None
    if (end_date - today).days <= KANBAN_ENTRY_DAYS:
        return AWAITING_ANALYSIS
    return None


def sync_contract_audit_stage(
    item: Contract, *, deadline_changed: bool = False, regularization_completed: bool = False
) -> None:
    """Sincroniza a entrada automática e a saída após regularização.

    Um contrato em "Aguardando Análise" retorna a "Não iniciado" quando a
    regularização é concluída e o alerta passa a "Regular". Etapas manuais
    avançadas não são alteradas por essa conclusão.
    """
    underlying_alert = alert_without_finalization(item)

    if (
        regularization_completed
        and item.auditStage == AWAITING_ANALYSIS
        and underlying_alert == "Regular"
        and not item.finalized
    ):
        item.auditStage = None
        item.auditStageEnteredAt = None
        return

    if deadline_changed and underlying_alert != "Vencido":
        item.finalized = False
        # O retorno ao backlog é automático somente para quem ainda aguardava
        # análise (ou estava finalizado e abriu um novo ciclo de vigência).
        # Demais etapas já trabalhadas são decisões manuais e permanecem.
        if item.auditStage in (None, AWAITING_ANALYSIS, FINALIZED):
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

    if item.finalized:
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
    ) == AWAITING_ANALYSIS:
        item.auditStage = AWAITING_ANALYSIS
        item.auditStageEnteredAt = utcnow()

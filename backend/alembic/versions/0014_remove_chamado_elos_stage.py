"""Remove a etapa "Chamado aberto no Elos" do Kanban de auditoria.

Contratos que estavam nessa etapa passam para "Aguardando Análise", para não
sumirem do quadro.

Revision ID: 0014_remove_chamado_elos_stage
Revises: 0014_internal_notifications
Create Date: 2026-11-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_remove_chamado_elos_stage"
down_revision: str | None = "0014_internal_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK_NAME = "Contract_auditStage_check"
_REMOVED_STAGE = "CHAMADO_ELES"
_FALLBACK_STAGE = "AGUARDANDO_ANALISE"
_ALLOWED = (
    "AGUARDANDO_ANALISE",
    "ANALISE_INTERNA_INPASA",
    "FORNECEDOR_CONTATADO",
    "EM_TRATATIVA",
    "EM_FINALIZACAO",
    "FINALIZADO",
)
_PREVIOUS_ALLOWED = (
    "AGUARDANDO_ANALISE",
    "CHAMADO_ELES",
    "ANALISE_INTERNA_INPASA",
    "FORNECEDOR_CONTATADO",
    "EM_TRATATIVA",
    "EM_FINALIZACAO",
    "FINALIZADO",
)


def _replace_stage_check(allowed: tuple[str, ...]) -> None:
    values = ", ".join(f"'{value}'" for value in allowed)
    op.drop_constraint(_CHECK_NAME, "Contract", type_="check")
    op.create_check_constraint(
        _CHECK_NAME, "Contract", f'"auditStage" IS NULL OR "auditStage" IN ({values})'
    )


def upgrade() -> None:
    op.execute(
        f'UPDATE "Contract" SET "auditStage" = \'{_FALLBACK_STAGE}\' '
        f'WHERE "auditStage" = \'{_REMOVED_STAGE}\''
    )
    _replace_stage_check(_ALLOWED)


def downgrade() -> None:
    # A distribuição original entre as etapas não é recuperável; apenas volta a
    # permitir o valor no banco.
    _replace_stage_check(_PREVIOUS_ALLOWED)

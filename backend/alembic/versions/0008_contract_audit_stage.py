"""Etapa persistida do Kanban de auditoria de contratos vencidos.

Revision ID: 0008_contract_audit_stage
Revises: 0007_overdue_open_unique
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_contract_audit_stage"
down_revision: str | None = "0007_overdue_open_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED = (
    "AGUARDANDO_ANALISE",
    "CHAMADO_ELES",
    "ANALISE_INTERNA_INPASA",
    "FORNECEDOR_CONTATADO",
    "EM_TRATATIVA",
    "EM_FINALIZACAO",
    "FINALIZADO",
)


def upgrade() -> None:
    op.add_column("Contract", sa.Column("auditStage", sa.String(length=40), nullable=True))
    allowed = ", ".join(f"'{value}'" for value in _ALLOWED)
    op.create_check_constraint(
        "Contract_auditStage_check", "Contract", f'"auditStage" IS NULL OR "auditStage" IN ({allowed})'
    )
    op.create_index("Contract_auditStage_idx", "Contract", ["auditStage"])


def downgrade() -> None:
    op.drop_index("Contract_auditStage_idx", table_name="Contract")
    op.drop_constraint("Contract_auditStage_check", "Contract", type_="check")
    op.drop_column("Contract", "auditStage")

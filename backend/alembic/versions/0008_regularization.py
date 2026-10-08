"""Campos de acompanhamento da regularização já aplicados em produção.

Revision ID: 0008_regularization
Revises: 0007_overdue_open_unique
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_regularization"
down_revision: str | None = "0007_overdue_open_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in [
        sa.Column("regularizationStage", sa.String(40)),
        sa.Column("regularizationResponsible", sa.String(180)),
        sa.Column("regularizationDeadline", sa.Date()),
        sa.Column("regularizationNotes", sa.Text()),
        sa.Column(
            "regularizationHistory",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    ]:
        op.add_column("Contract", column)
    op.create_check_constraint(
        "Contract_regularizationStage_check",
        "Contract",
        '"regularizationStage" IS NULL OR "regularizationStage" IN ('
        "'aguardando_analise','chamados_elos','analise_interna',"
        "'fornecedor_contatado','em_tratativa','em_finalizacao')",
    )


def downgrade() -> None:
    op.drop_constraint("Contract_regularizationStage_check", "Contract", type_="check")
    for name in [
        "regularizationHistory",
        "regularizationNotes",
        "regularizationDeadline",
        "regularizationResponsible",
        "regularizationStage",
    ]:
        op.drop_column("Contract", name)

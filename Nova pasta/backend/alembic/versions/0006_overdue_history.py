"""Histórico real de regularização dos contratos vencidos (Dashboard).

Cria `OverdueContractTracking` (um ciclo por ida de um contrato a "Vencido",
com data de resolução quando ele deixa de estar vencido) e
`OverdueDailySnapshot` (foto diária org-wide de quantos estão vencidos e
quantos já foram regularizados desde que o acompanhamento começou). Os dois
são preenchidos sob demanda (reconciliação a cada acesso ao Dashboard), não
por um job — só adiciona estruturas, nenhuma tabela existente muda.

Revision ID: 0006_overdue_history
Revises: 0005_notification_teams
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_overdue_history"
down_revision: str | None = "0005_notification_teams"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "OverdueContractTracking",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("contractId", sa.String(), nullable=False),
        sa.Column("firstSeenOverdueAt", sa.Date(), nullable=False),
        sa.Column("resolvedAt", sa.Date(), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["contractId"], ["Contract.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "OverdueContractTracking_contractId_idx", "OverdueContractTracking", ["contractId"], unique=False
    )
    op.create_index(
        "OverdueContractTracking_resolvedAt_idx", "OverdueContractTracking", ["resolvedAt"], unique=False
    )

    op.create_table(
        "OverdueDailySnapshot",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("resolvedCumulative", sa.Integer(), nullable=False),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("OverdueDailySnapshot_date_key", "OverdueDailySnapshot", ["date"], unique=True)


def downgrade() -> None:
    op.drop_index("OverdueDailySnapshot_date_key", table_name="OverdueDailySnapshot")
    op.drop_table("OverdueDailySnapshot")
    op.drop_index("OverdueContractTracking_resolvedAt_idx", table_name="OverdueContractTracking")
    op.drop_index("OverdueContractTracking_contractId_idx", table_name="OverdueContractTracking")
    op.drop_table("OverdueContractTracking")

"""No máximo um ciclo de vencido em aberto por contrato.

A reconciliação do histórico de vencidos roda num GET e podia ser executada em
paralelo, abrindo dois ciclos para o mesmo contrato. Esta migração remove os
ciclos em aberto duplicados (mantém o mais antigo; os extras são artefatos da
corrida, não regularizações reais) e cria um índice único parcial para que o
banco impeça a duplicação daqui em diante.

Revision ID: 0007_overdue_open_unique
Revises: 0006_overdue_history
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_overdue_open_unique"
down_revision: str | None = "0006_overdue_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM "OverdueContractTracking" t
        USING (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY "contractId"
                       ORDER BY "firstSeenOverdueAt", "createdAt", id
                   ) AS rn
            FROM "OverdueContractTracking"
            WHERE "resolvedAt" IS NULL
        ) d
        WHERE t.id = d.id AND d.rn > 1
        """
    )
    op.create_index(
        "OverdueContractTracking_open_contractId_key",
        "OverdueContractTracking",
        ["contractId"],
        unique=True,
        postgresql_where=sa.text('"resolvedAt" IS NULL'),
    )


def downgrade() -> None:
    op.drop_index("OverdueContractTracking_open_contractId_key", table_name="OverdueContractTracking")

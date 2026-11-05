"""Preserva ciclos já resolvidos quando um contrato é excluído.

Antes, `OverdueContractTracking.contractId` usava `ON DELETE CASCADE`: excluir
um contrato apagava também os ciclos já regularizados dele e o acumulado do
gráfico "Histórico de vigência dos Contratos Vencidos" diminuía — apesar de a
série ser cumulativa.

A coluna passa a aceitar NULL e o FK vira `ON DELETE SET NULL`. O serviço de
exclusão remove apenas os ciclos em aberto (que deixaram de existir); os
resolvidos permanecem como histórico, sem contrato associado.

Revision ID: 0015_overdue_preserve_deleted
Revises: 0014_remove_chamado_elos_stage
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_overdue_preserve_deleted"
down_revision: str | None = "0014_remove_chamado_elos_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "OverdueContractTracking_contractId_fkey"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "OverdueContractTracking", type_="foreignkey")
    op.alter_column(
        "OverdueContractTracking",
        "contractId",
        existing_type=sa.String(),
        nullable=True,
    )
    op.create_foreign_key(
        _FK_NAME,
        "OverdueContractTracking",
        "Contract",
        ["contractId"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )


def downgrade() -> None:
    # O rollback não recupera os vínculos perdidos: ciclos de contratos já
    # excluídos precisam sair para a coluna voltar a ser NOT NULL.
    op.execute('DELETE FROM "OverdueContractTracking" WHERE "contractId" IS NULL')
    op.drop_constraint(_FK_NAME, "OverdueContractTracking", type_="foreignkey")
    op.alter_column(
        "OverdueContractTracking",
        "contractId",
        existing_type=sa.String(),
        nullable=False,
    )
    op.create_foreign_key(
        _FK_NAME,
        "OverdueContractTracking",
        "Contract",
        ["contractId"],
        ["id"],
        ondelete="CASCADE",
        onupdate="CASCADE",
    )

"""Compatibilidade com a revisão já registrada em produção.

Revision ID: 0010_contract_dilation
Revises: 0009_contract_audit_stage
Create Date: 2026-10-15

Essa revisão foi gravada anteriormente no ``alembic_version`` de produção,
mas seu arquivo não chegou ao histórico Git. O backend atualmente publicado
funciona sobre esse banco sem depender de alterações adicionais. Mantemos a
revisão como ponte explícita e sem DDL para restaurar uma cadeia Alembic única,
permitindo que instalações novas e o banco existente avancem com segurança.
"""

from collections.abc import Sequence

revision: str = "0010_contract_dilation"
down_revision: str | None = "0009_contract_audit_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""Normaliza etapas removidas no histórico do workspace de auditoria.

A migração 0014 removeu "CHAMADO_ELES" da coluna `Contract.auditStage`, mas as
atividades já registradas em `ContractAuditActivity` mantiveram o valor em
`fromStage`/`toStage`. O workspace desses contratos falhava na validação da
resposta, pois a etapa não faz mais parte do enum atual.

Revision ID: 0016_normalize_audit_stages
Revises: 0015_overdue_preserve_deleted
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_normalize_audit_stages"
down_revision: str | None = "0015_overdue_preserve_deleted"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REMOVED_STAGE = "CHAMADO_ELES"
_FALLBACK_STAGE = "AGUARDANDO_ANALISE"


def upgrade() -> None:
    for column in ("fromStage", "toStage"):
        op.execute(
            f'UPDATE "ContractAuditActivity" SET "{column}" = \'{_FALLBACK_STAGE}\' '
            f'WHERE "{column}" = \'{_REMOVED_STAGE}\''
        )


def downgrade() -> None:
    # A distribuição original entre as etapas não é recuperável.
    pass

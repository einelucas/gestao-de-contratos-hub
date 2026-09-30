"""Provedor usado em cada tentativa de envio de ContractNotification.

Revision ID: 0004_notification_provider
Revises: 0003_contract_alerts
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_notification_provider"
down_revision: str | None = "0003_contract_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ContractNotification", sa.Column("provider", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("ContractNotification", "provider")

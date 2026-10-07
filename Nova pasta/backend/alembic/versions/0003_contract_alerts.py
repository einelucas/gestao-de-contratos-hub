"""Campos de alerta de vencimento em Contract e histórico ContractNotification.

Revision ID: 0003_contract_alerts
Revises: 0002_contracts_domain
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_contract_alerts"
down_revision: str | None = "0002_contracts_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CRITICALITY = ("BAIXA", "MEDIA", "ALTA")
_NOTIFICATION_TYPE = ("ANTECEDENCIA", "VENCIMENTO", "VENCIDO")
_NOTIFICATION_STATUS = ("PENDING", "SENT", "FAILED", "SKIPPED")


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(*_CRITICALITY, name="ContractCriticality").create(bind, checkfirst=True)
    postgresql.ENUM(*_NOTIFICATION_TYPE, name="ContractNotificationType").create(bind, checkfirst=True)
    postgresql.ENUM(*_NOTIFICATION_STATUS, name="ContractNotificationStatus").create(bind, checkfirst=True)

    # Contratos existentes entram com notify=false: nenhum alerta é disparado
    # até alguém definir responsável e ativar a notificação.
    op.add_column("Contract", sa.Column("notify", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("Contract", sa.Column("noticeDays", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("Contract", sa.Column("responsibleUserId", sa.String(), nullable=True))
    op.add_column("Contract", sa.Column("responsibleEmail", sa.String(length=320), nullable=True))
    op.add_column(
        "Contract", sa.Column("autoRenewal", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "Contract",
        sa.Column(
            "criticality",
            postgresql.ENUM(*_CRITICALITY, name="ContractCriticality", create_type=False),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "Contract_responsibleUserId_fkey",
        "Contract",
        "User",
        ["responsibleUserId"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )
    op.create_check_constraint("Contract_noticeDays_check", "Contract", '"noticeDays" BETWEEN 1 AND 365')
    op.create_index("Contract_responsibleUserId_idx", "Contract", ["responsibleUserId"], unique=False)
    op.create_index("Contract_notify_endDate_idx", "Contract", ["notify", "endDate"], unique=False)

    op.create_table(
        "ContractNotification",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("contractId", sa.String(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(*_NOTIFICATION_TYPE, name="ContractNotificationType", create_type=False),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("referenceDate", sa.Date(), nullable=False),
        sa.Column("noticeDays", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contractEndDate", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*_NOTIFICATION_STATUS, name="ContractNotificationStatus", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sentAt", postgresql.TIMESTAMP(precision=3), nullable=True),
        sa.Column("lastAttemptAt", postgresql.TIMESTAMP(precision=3), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["contractId"], ["Contract.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ContractNotification_dedup_key",
        "ContractNotification",
        ["contractId", "type", "referenceDate", "noticeDays", "recipient"],
        unique=True,
    )
    op.create_index(
        "ContractNotification_contractId_idx", "ContractNotification", ["contractId"], unique=False
    )
    op.create_index(
        "ContractNotification_status_attempts_idx",
        "ContractNotification",
        ["status", "attempts"],
        unique=False,
    )
    op.create_index(
        "ContractNotification_createdAt_idx", "ContractNotification", ["createdAt"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ContractNotification_createdAt_idx", table_name="ContractNotification")
    op.drop_index("ContractNotification_status_attempts_idx", table_name="ContractNotification")
    op.drop_index("ContractNotification_contractId_idx", table_name="ContractNotification")
    op.drop_index("ContractNotification_dedup_key", table_name="ContractNotification")
    op.drop_table("ContractNotification")

    op.drop_index("Contract_notify_endDate_idx", table_name="Contract")
    op.drop_index("Contract_responsibleUserId_idx", table_name="Contract")
    op.drop_constraint("Contract_noticeDays_check", "Contract", type_="check")
    op.drop_constraint("Contract_responsibleUserId_fkey", "Contract", type_="foreignkey")
    op.drop_column("Contract", "criticality")
    op.drop_column("Contract", "autoRenewal")
    op.drop_column("Contract", "responsibleEmail")
    op.drop_column("Contract", "responsibleUserId")
    op.drop_column("Contract", "noticeDays")
    op.drop_column("Contract", "notify")

    bind = op.get_bind()
    postgresql.ENUM(name="ContractNotificationStatus").drop(bind, checkfirst=True)
    postgresql.ENUM(name="ContractNotificationType").drop(bind, checkfirst=True)
    postgresql.ENUM(name="ContractCriticality").drop(bind, checkfirst=True)

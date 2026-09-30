"""Equipes de notificação por setor e régua fixa de alertas.

Cria NotificationTeam / NotificationTeamMember, liga o contrato a uma equipe
(`notificationTeamId`), registra quando a notificação foi ligada
(`notifyEnabledOn`) e de qual equipe veio cada envio. Só adiciona estruturas:
contratos existentes continuam com notify=false e sem equipe.

Revision ID: 0005_notification_teams
Revises: 0004_notification_provider
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_notification_teams"
down_revision: str | None = "0004_notification_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "NotificationTeam",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("sectorId", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["sectorId"], ["Sector.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "NotificationTeam_sectorId_name_key", "NotificationTeam", ["sectorId", "name"], unique=True
    )
    op.create_index("NotificationTeam_sectorId_idx", "NotificationTeam", ["sectorId"], unique=False)

    op.create_table(
        "NotificationTeamMember",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("teamId", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["teamId"], ["NotificationTeam.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "NotificationTeamMember_teamId_email_key", "NotificationTeamMember", ["teamId", "email"], unique=True
    )
    op.create_index("NotificationTeamMember_teamId_idx", "NotificationTeamMember", ["teamId"], unique=False)

    op.add_column("Contract", sa.Column("notificationTeamId", sa.String(), nullable=True))
    op.add_column("Contract", sa.Column("notifyEnabledOn", sa.Date(), nullable=True))
    op.create_foreign_key(
        "Contract_notificationTeamId_fkey",
        "Contract",
        "NotificationTeam",
        ["notificationTeamId"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )
    op.create_index("Contract_notificationTeamId_idx", "Contract", ["notificationTeamId"], unique=False)

    op.add_column("ContractNotification", sa.Column("notificationTeamId", sa.String(), nullable=True))
    op.create_foreign_key(
        "ContractNotification_notificationTeamId_fkey",
        "ContractNotification",
        "NotificationTeam",
        ["notificationTeamId"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ContractNotification_notificationTeamId_fkey", "ContractNotification", type_="foreignkey"
    )
    op.drop_column("ContractNotification", "notificationTeamId")
    op.drop_index("Contract_notificationTeamId_idx", table_name="Contract")
    op.drop_constraint("Contract_notificationTeamId_fkey", "Contract", type_="foreignkey")
    op.drop_column("Contract", "notifyEnabledOn")
    op.drop_column("Contract", "notificationTeamId")
    op.drop_index("NotificationTeamMember_teamId_idx", table_name="NotificationTeamMember")
    op.drop_index("NotificationTeamMember_teamId_email_key", table_name="NotificationTeamMember")
    op.drop_table("NotificationTeamMember")
    op.drop_index("NotificationTeam_sectorId_idx", table_name="NotificationTeam")
    op.drop_index("NotificationTeam_sectorId_name_key", table_name="NotificationTeam")
    op.drop_table("NotificationTeam")

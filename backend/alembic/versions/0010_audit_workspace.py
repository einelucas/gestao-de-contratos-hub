"""Workspace colaborativo da auditoria.

Revision ID: 0010_audit_workspace
Revises: 0009_contract_audit_stage
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_audit_workspace"
down_revision: str | None = "0009_contract_audit_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "Contract",
        sa.Column("auditStageEnteredAt", postgresql.TIMESTAMP(precision=3), nullable=True),
    )
    op.execute(
        'UPDATE "Contract" SET "auditStageEnteredAt" = "updatedAt" '
        'WHERE "auditStage" IS NOT NULL AND "auditStageEnteredAt" IS NULL'
    )

    op.create_table(
        "ContractAuditUpdate",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("contractId", sa.String(), nullable=False),
        sa.Column("authorId", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("mentionedUserIds", sa.JSON(), nullable=False),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["authorId"], ["User.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["contractId"], ["Contract.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ContractAuditUpdate_contractId_createdAt_idx",
        "ContractAuditUpdate",
        ["contractId", "createdAt"],
    )
    op.create_table(
        "ContractAuditAttachment",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("updateId", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("contentType", sa.String(length=160), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(
            ["updateId"], ["ContractAuditUpdate.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ContractAuditAttachment_updateId_idx", "ContractAuditAttachment", ["updateId"])
    op.create_table(
        "ContractAuditActivity",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("contractId", sa.String(), nullable=False),
        sa.Column("actorId", sa.String(), nullable=True),
        sa.Column("type", sa.String(length=24), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("fromStage", sa.String(length=40), nullable=True),
        sa.Column("toStage", sa.String(length=40), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["actorId"], ["User.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["contractId"], ["Contract.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ContractAuditActivity_contractId_createdAt_idx",
        "ContractAuditActivity",
        ["contractId", "createdAt"],
    )


def downgrade() -> None:
    op.drop_index("ContractAuditActivity_contractId_createdAt_idx", table_name="ContractAuditActivity")
    op.drop_table("ContractAuditActivity")
    op.drop_index("ContractAuditAttachment_updateId_idx", table_name="ContractAuditAttachment")
    op.drop_table("ContractAuditAttachment")
    op.drop_index("ContractAuditUpdate_contractId_createdAt_idx", table_name="ContractAuditUpdate")
    op.drop_table("ContractAuditUpdate")
    op.drop_column("Contract", "auditStageEnteredAt")

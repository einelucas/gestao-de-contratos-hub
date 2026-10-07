"""Base compartilhada do Gestão de Contratos.

Revision ID: 0001_shared_base
Revises:
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_shared_base"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role_enum = postgresql.ENUM("VIEWER", "ANALYST", "ADMIN", name="Role")
    role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "User",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("emailVerified", sa.Boolean(), nullable=False),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("role", postgresql.ENUM("VIEWER", "ANALYST", "ADMIN", name="Role", create_type=False), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("authProvider", sa.String(), nullable=False),
        sa.Column("externalUserId", sa.String(), nullable=True),
        sa.Column("lastLoginAt", postgresql.TIMESTAMP(precision=3), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("User_email_idx", "User", ["email"], unique=False)
    op.create_index("User_email_key", "User", ["email"], unique=True)
    op.create_index("User_externalUserId_idx", "User", ["externalUserId"], unique=False)

    op.create_table(
        "Verification",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("expiresAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("Verification_identifier_idx", "Verification", ["identifier"], unique=False)

    op.create_table(
        "Account",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("accountId", sa.String(), nullable=False),
        sa.Column("providerId", sa.String(), nullable=False),
        sa.Column("accessToken", sa.String(), nullable=True),
        sa.Column("refreshToken", sa.String(), nullable=True),
        sa.Column("accessTokenExpiresAt", postgresql.TIMESTAMP(precision=3), nullable=True),
        sa.Column("refreshTokenExpiresAt", postgresql.TIMESTAMP(precision=3), nullable=True),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("idToken", sa.String(), nullable=True),
        sa.Column("password", sa.String(), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["userId"], ["User.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("Account_providerId_accountId_key", "Account", ["providerId", "accountId"], unique=True)
    op.create_index("Account_userId_idx", "Account", ["userId"], unique=False)

    op.create_table(
        "AuditLog",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("entityId", sa.String(), nullable=True),
        sa.Column("previousData", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("newData", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["userId"], ["User.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("AuditLog_createdAt_idx", "AuditLog", ["createdAt"], unique=False)
    op.create_index("AuditLog_entity_entityId_idx", "AuditLog", ["entity", "entityId"], unique=False)
    op.create_index("AuditLog_userId_idx", "AuditLog", ["userId"], unique=False)

    op.create_table(
        "Session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expiresAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("ipAddress", sa.String(), nullable=True),
        sa.Column("userAgent", sa.String(), nullable=True),
        sa.Column("createdAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column("updatedAt", postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(["userId"], ["User.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("Session_token_key", "Session", ["token"], unique=True)
    op.create_index("Session_userId_idx", "Session", ["userId"], unique=False)


def downgrade() -> None:
    op.drop_index("Session_userId_idx", table_name="Session")
    op.drop_index("Session_token_key", table_name="Session")
    op.drop_table("Session")

    op.drop_index("AuditLog_userId_idx", table_name="AuditLog")
    op.drop_index("AuditLog_entity_entityId_idx", table_name="AuditLog")
    op.drop_index("AuditLog_createdAt_idx", table_name="AuditLog")
    op.drop_table("AuditLog")

    op.drop_index("Account_userId_idx", table_name="Account")
    op.drop_index("Account_providerId_accountId_key", table_name="Account")
    op.drop_table("Account")

    op.drop_index("Verification_identifier_idx", table_name="Verification")
    op.drop_table("Verification")

    op.drop_index("User_externalUserId_idx", table_name="User")
    op.drop_index("User_email_key", table_name="User")
    op.drop_index("User_email_idx", table_name="User")
    op.drop_table("User")

    postgresql.ENUM(name="Role").drop(op.get_bind(), checkfirst=True)

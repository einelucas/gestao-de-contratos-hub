"""Notificações internas de menções e lembretes pessoais de contratos.

Revision ID: 0014_internal_notifications
Revises: 0013_local_user_password
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_internal_notifications"
down_revision = "0013_local_user_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "InAppNotification",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("userId", sa.String(), sa.ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
        sa.Column("contractId", sa.String(), sa.ForeignKey("Contract.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
        sa.Column("actorId", sa.String(), sa.ForeignKey("User.id", ondelete="SET NULL", onupdate="CASCADE")),
        sa.Column("auditUpdateId", sa.String(), sa.ForeignKey("ContractAuditUpdate.id", ondelete="CASCADE", onupdate="CASCADE")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("scheduledAt", sa.TIMESTAMP(precision=3), nullable=False),
        sa.Column("readAt", sa.TIMESTAMP(precision=3)),
        sa.Column("createdAt", sa.TIMESTAMP(precision=3), nullable=False),
        sa.CheckConstraint("kind IN ('MENTION', 'REMINDER')", name="InAppNotification_kind_check"),
    )
    op.create_index("InAppNotification_user_due_idx", "InAppNotification", ["userId", "scheduledAt"])
    op.create_index("InAppNotification_contract_idx", "InAppNotification", ["contractId"])
    op.create_index("InAppNotification_user_read_idx", "InAppNotification", ["userId", "readAt"])
    op.create_index("InAppNotification_mention_key", "InAppNotification", ["userId", "auditUpdateId"], unique=True)

    # Menções feitas antes desta versão também aparecem na nova central.
    # gen_random_uuid() é nativo do PostgreSQL moderno usado pelo Neon.
    op.execute("""
        INSERT INTO "InAppNotification"
            ("id", "userId", "contractId", "actorId", "auditUpdateId",
             "kind", "message", "scheduledAt", "readAt", "createdAt")
        SELECT gen_random_uuid()::text, recipient.id, upd."contractId",
               upd."authorId", upd.id, 'MENTION',
               left(upd.text, 500), upd."createdAt", NULL, upd."createdAt"
        FROM "ContractAuditUpdate" upd
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(upd."mentionedUserIds"::jsonb, '[]'::jsonb)
        ) AS member(user_id)
        JOIN "User" recipient ON recipient.id = member.user_id
        LEFT JOIN "UserSectorPermission" sector_permission
            ON sector_permission."userId" = recipient.id
           AND sector_permission."sectorId" = (
               SELECT c."sectorId" FROM "Contract" c WHERE c.id = upd."contractId"
           )
        WHERE recipient.active IS TRUE
          AND recipient.id IS DISTINCT FROM upd."authorId"
          AND (
              recipient.role::text = 'ADMIN'
              OR sector_permission."canView" IS TRUE
              OR sector_permission."canEdit" IS TRUE
          )
        ON CONFLICT ("userId", "auditUpdateId") DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("InAppNotification_mention_key", table_name="InAppNotification")
    op.drop_index("InAppNotification_user_read_idx", table_name="InAppNotification")
    op.drop_index("InAppNotification_contract_idx", table_name="InAppNotification")
    op.drop_index("InAppNotification_user_due_idx", table_name="InAppNotification")
    op.drop_table("InAppNotification")

"""Credenciais locais com troca obrigatória da senha inicial.

Revision ID: 0013_local_user_password
Revises: 0012_contract_dilation_fields
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_local_user_password"
down_revision: str | None = "0012_contract_dilation_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("User")}
    if "passwordChangeRequired" not in columns:
        op.add_column(
            "User",
            sa.Column(
                "passwordChangeRequired",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("User")}
    if "passwordChangeRequired" in columns:
        op.drop_column("User", "passwordChangeRequired")

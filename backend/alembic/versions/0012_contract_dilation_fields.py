"""Campos de dilação contratual.

Revision ID: 0012_contract_dilation_fields
Revises: 0011_audit_workspace
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_contract_dilation_fields"
down_revision: str | None = "0011_audit_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("Contract")}

    if "dilation" not in columns:
        op.add_column(
            "Contract",
            sa.Column(
                "dilation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if "dilationEndDate" not in columns:
        op.add_column(
            "Contract",
            sa.Column("dilationEndDate", sa.Date(), nullable=True),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("Contract")}
    if "Contract_dilationEndDate_idx" not in indexes:
        op.create_index(
            "Contract_dilationEndDate_idx",
            "Contract",
            ["dilationEndDate"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("Contract")}
    if "Contract_dilationEndDate_idx" in indexes:
        op.drop_index("Contract_dilationEndDate_idx", table_name="Contract")

    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("Contract")}
    if "dilationEndDate" in columns:
        op.drop_column("Contract", "dilationEndDate")
    if "dilation" in columns:
        op.drop_column("Contract", "dilation")

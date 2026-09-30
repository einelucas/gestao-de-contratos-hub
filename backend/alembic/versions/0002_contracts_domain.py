"""Domínio inicial de Gestão de Contratos.

Revision ID: 0002_contracts_domain
Revises: 0001_shared_base
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_contracts_domain"
down_revision: str | None = "0001_shared_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "Sector",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("acronym", sa.String(length=24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("createdAt", sa.TIMESTAMP(), nullable=False),
        sa.Column("updatedAt", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("Sector_slug_key", "Sector", ["slug"], unique=True)
    op.create_index("Sector_active_idx", "Sector", ["active"], unique=False)

    op.create_table(
        "Supplier",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("createdAt", sa.TIMESTAMP(), nullable=False),
        sa.Column("updatedAt", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("Supplier_name_key", "Supplier", ["name"], unique=True)

    op.create_table(
        "Contract",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("sectorId", sa.String(), nullable=False),
        sa.Column("supplierId", sa.String(), nullable=False),
        sa.Column("contractNumber", sa.String(length=80), nullable=False),
        sa.Column("serviceDescription", sa.Text(), nullable=False, server_default=""),
        sa.Column("serviceValue", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("ownMaterialValue", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("thirdPartyMaterialValue", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("totalValue", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("startDate", sa.Date(), nullable=True),
        sa.Column("endDate", sa.Date(), nullable=True),
        sa.Column("unit", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("finalized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("createdAt", sa.TIMESTAMP(), nullable=False),
        sa.Column("updatedAt", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["sectorId"], ["Sector.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["supplierId"], ["Supplier.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sectorId", "contractNumber", name="Contract_sectorId_contractNumber_key"),
    )
    op.create_index("Contract_sectorId_idx", "Contract", ["sectorId"], unique=False)
    op.create_index("Contract_supplierId_idx", "Contract", ["supplierId"], unique=False)
    op.create_index("Contract_endDate_idx", "Contract", ["endDate"], unique=False)
    op.create_index("Contract_unit_idx", "Contract", ["unit"], unique=False)

    op.create_table(
        "UserSectorPermission",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("sectorId", sa.String(), nullable=False),
        sa.Column("canView", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("canEdit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("createdAt", sa.TIMESTAMP(), nullable=False),
        sa.Column("updatedAt", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["userId"], ["User.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["sectorId"], ["Sector.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("userId", "sectorId", name="UserSectorPermission_userId_sectorId_key"),
    )
    op.create_index("UserSectorPermission_userId_idx", "UserSectorPermission", ["userId"], unique=False)
    op.create_index("UserSectorPermission_sectorId_idx", "UserSectorPermission", ["sectorId"], unique=False)


def downgrade() -> None:
    op.drop_index("UserSectorPermission_sectorId_idx", table_name="UserSectorPermission")
    op.drop_index("UserSectorPermission_userId_idx", table_name="UserSectorPermission")
    op.drop_table("UserSectorPermission")
    op.drop_index("Contract_unit_idx", table_name="Contract")
    op.drop_index("Contract_endDate_idx", table_name="Contract")
    op.drop_index("Contract_supplierId_idx", table_name="Contract")
    op.drop_index("Contract_sectorId_idx", table_name="Contract")
    op.drop_table("Contract")
    op.drop_index("Supplier_name_key", table_name="Supplier")
    op.drop_table("Supplier")
    op.drop_index("Sector_active_idx", table_name="Sector")
    op.drop_index("Sector_slug_key", table_name="Sector")
    op.drop_table("Sector")

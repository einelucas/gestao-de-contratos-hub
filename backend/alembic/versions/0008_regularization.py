"""Contract regularization board and shared history."""

import sqlalchemy as sa

from alembic import op

revision = "0008_regularization"
down_revision = "0007_overdue_open_unique"
branch_labels = None
depends_on = None


def upgrade():
    for column in [
        sa.Column("regularizationStage", sa.String(40)),
        sa.Column("regularizationResponsible", sa.String(180)),
        sa.Column("regularizationDeadline", sa.Date()),
        sa.Column("regularizationNotes", sa.Text()),
        sa.Column("regularizationHistory", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    ]:
        op.add_column("Contract", column)
    op.create_check_constraint(
        "Contract_regularizationStage_check",
        "Contract",
        '"regularizationStage" IS NULL OR "regularizationStage" IN ('
        "'aguardando_analise','chamados_elos','analise_interna',"
        "'fornecedor_contatado','em_tratativa','em_finalizacao')",
    )


def downgrade():
    op.drop_constraint("Contract_regularizationStage_check", "Contract", type_="check")
    for name in [
        "regularizationHistory",
        "regularizationNotes",
        "regularizationDeadline",
        "regularizationResponsible",
        "regularizationStage",
    ]:
        op.drop_column("Contract", name)

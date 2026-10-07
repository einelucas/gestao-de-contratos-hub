"""Standalone isolated SQLite checks; no application database is accessed."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/regularization_test")
import pytest
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def compile_jsonb(element, compiler, **kw):
    return "JSON"


import app.models
from app.core.database import Base
from app.core.auth import CurrentUser
from app.core.errors import DomainError
from app.models.contracts import Contract, Sector, Supplier
from app.models.user import User, Role
from app.modules.contracts import service, summary
from app.modules.contracts.schemas import ContractUpdateIn


async def test_shared_board_and_completion():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        user = User(name="Samuel", email="samuel@example.com", role=Role.ADMIN)
        sector = Sector(slug="projects", name="Projetos", acronym="PRO")
        supplier = Supplier(name="Fornecedor")
        session.add_all([user, sector, supplier])
        await session.flush()
        contract = Contract(
            sectorId=sector.id,
            supplierId=supplier.id,
            contractNumber="100",
            unit="Dourados",
            endDate=date(2020, 1, 1),
        )
        session.add(contract)
        await session.commit()
        actor = CurrentUser(id=user.id, name=user.name, email=user.email, role=Role.ADMIN, active=True)
        out = await service.update_contract(
            session,
            contract.id,
            ContractUpdateIn(regularization_stage="aguardando_analise", regularization_responsible="Samuel"),
            actor,
        )
        assert out.alert == "Regularizacao" and out.situation == "Vencido"
        assert len(out.regularization_history) == 1
        report = await summary.build_summary(session, actor)
        assert report.kpis.vencido == 0 and report.kpis.regularization == 1
        assert report.kpis.on_time == 0 and report.kpis.on_time_base == 1
        assert sum(b.count for b in report.deadlines) == 1
        out = await service.update_contract(
            session, contract.id, ContractUpdateIn(regularization_stage="chamados_elos"), actor
        )
        assert len(out.regularization_history) == 2
        with pytest.raises(DomainError):
            await service.update_contract(
                session, contract.id, ContractUpdateIn(regularization_stage=None), actor
            )
        await session.rollback()
        out = await service.update_contract(
            session, out.id, ContractUpdateIn(regularization_stage=None, end_date=date(2035, 1, 1)), actor
        )
        assert out.alert == "Regular" and out.regularization_stage is None
        assert out.regularization_history[-1]["stage"] is None
    await engine.dispose()

"""Seed idempotente do CSV inicial de contratos.

Uso (depois de `alembic upgrade head`):
    python scripts/seed_contracts.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.contracts import Contract, Sector, Supplier  # noqa: E402

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "relacao_contratos.csv"
SECTOR_SLUG = "projetos-arquitetura"
SECTOR_NAME = "Projetos e Arquitetura"
SECTOR_ACRONYM = "P&A"


def money(value: str | None) -> Decimal:
    raw = (value or "").strip()
    if not raw:
        return Decimal("0.00")
    normalized = raw.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {value!r}") from exc


def parse_date(value: str | None):
    raw = (value or "").strip()
    return datetime.strptime(raw, "%d/%m/%Y").date() if raw else None


def is_finalized(value: str | None) -> bool:
    return "finalizado" in (value or "").lower()


async def get_or_create_sector(session) -> Sector:
    result = await session.execute(select(Sector).where(Sector.slug == SECTOR_SLUG))
    sector = result.scalar_one_or_none()
    if sector is None:
        sector = Sector(slug=SECTOR_SLUG, name=SECTOR_NAME, acronym=SECTOR_ACRONYM, active=True)
        session.add(sector)
        await session.flush()
    return sector


async def get_or_create_supplier(session, name: str) -> Supplier:
    clean = " ".join(name.strip().split())
    result = await session.execute(select(Supplier).where(func.lower(Supplier.name) == clean.lower()))
    supplier = result.scalar_one_or_none()
    if supplier is None:
        supplier = Supplier(name=clean, active=True)
        session.add(supplier)
        await session.flush()
    return supplier


async def seed() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"CSV não encontrado: {CSV_PATH}")
    created = 0
    updated = 0
    async with SessionLocal() as session:
        sector = await get_or_create_sector(session)
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                number = (row.get("Contrato") or "").strip()
                if not number:
                    continue
                supplier = await get_or_create_supplier(session, row.get("Fornecedor") or "Fornecedor não informado")
                result = await session.execute(
                    select(Contract).where(Contract.sectorId == sector.id, Contract.contractNumber == number)
                )
                item = result.scalar_one_or_none()
                values = dict(
                    sectorId=sector.id,
                    supplierId=supplier.id,
                    contractNumber=number,
                    serviceDescription=(row.get("Prestação") or "").strip(),
                    serviceValue=money(row.get("Valor Serviço")),
                    ownMaterialValue=money(row.get("Valor Material Proprio")),
                    thirdPartyMaterialValue=money(row.get("Valor Material Terceiros")),
                    totalValue=money(row.get("Valor Total")),
                    startDate=parse_date(row.get("Inicio Vigência")),
                    endDate=parse_date(row.get("Fim Vigência")),
                    unit=(row.get("Unidade") or "").strip(),
                    finalized=is_finalized(row.get("Situação")),
                    source="seed_csv",
                )
                if item is None:
                    session.add(Contract(**values))
                    created += 1
                else:
                    for key, value in values.items():
                        setattr(item, key, value)
                    updated += 1
        await session.commit()
    print(f"Seed concluído: {created} contratos criados, {updated} atualizados.")


if __name__ == "__main__":
    asyncio.run(seed())

"""Catálogo compartilhado pelos fluxos de cadastro e importação de contratos."""

from __future__ import annotations

import unicodedata

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contracts import Supplier

_SUPPLIER_CATALOG_LOCK = 0x5A77_11E2


def supplier_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", " ".join(name.split()).casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


async def lock_supplier_catalog(session: AsyncSession) -> None:
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SUPPLIER_CATALOG_LOCK})


async def suppliers_by_name(session: AsyncSession) -> dict[str, Supplier]:
    rows = (
        await session.execute(
            select(Supplier).order_by(Supplier.active.desc(), Supplier.createdAt, Supplier.id)
        )
    ).scalars().all()
    by_name: dict[str, Supplier] = {}
    for supplier in rows:
        by_name.setdefault(supplier_key(supplier.name), supplier)
    return by_name


async def get_or_create_supplier(session: AsyncSession, name: str) -> Supplier:
    # Quem chama obtém o lock antes de bloquear ou gravar contratos.
    supplier = (await suppliers_by_name(session)).get(supplier_key(name))
    if supplier is None:
        supplier = Supplier(name=" ".join(name.split()), active=True)
        session.add(supplier)
        await session.flush()
    return supplier

"""Tipos e helpers comuns aos modelos SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import MappedColumn, mapped_column


# IDs compartilhados são armazenados como texto e gerados na aplicação.
def uuid_pk() -> MappedColumn[str]:
    return mapped_column(
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# Timestamp com precisão de milissegundos e sem timezone, padrão da base compartilhada.
Timestamp3 = TIMESTAMP(precision=3, timezone=False)

__all__ = ["Timestamp3", "uuid_pk", "utcnow"]

"""Base Pydantic compartilhada: aceita snake_case e serializa em camelCase."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# Validação simples de e-mail compartilhada pelos módulos (sem dependência extra).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

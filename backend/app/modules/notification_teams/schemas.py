from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.shared.schema import EMAIL_PATTERN, CamelModel

_EMAIL_RE = re.compile(EMAIL_PATTERN)


def normalize_email(value: str) -> str:
    clean = value.strip().lower()
    if not clean or not _EMAIL_RE.match(clean):
        raise ValueError(f"E-mail inválido: {value!r}")
    return clean


class TeamMemberOut(CamelModel):
    id: str
    name: str | None
    email: str
    active: bool


class NotificationTeamOut(CamelModel):
    id: str
    name: str
    sector_id: str
    sector_name: str
    active: bool
    members: list[TeamMemberOut]
    active_member_count: int
    contract_count: int
    created_at: datetime
    updated_at: datetime


class NotificationTeamListOut(CamelModel):
    items: list[NotificationTeamOut]


class TeamMemberIn(CamelModel):
    # Com `id`, atualiza o membro existente; sem, cria um novo.
    id: str | None = None
    name: str | None = Field(default=None, max_length=180)
    email: str = Field(max_length=320)
    active: bool = True

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


def _unique_emails(members: list[TeamMemberIn]) -> None:
    emails = [member.email for member in members]
    duplicated = sorted({email for email in emails if emails.count(email) > 1})
    if duplicated:
        raise ValueError(f"E-mail repetido na equipe: {', '.join(duplicated)}")


class NotificationTeamCreateIn(CamelModel):
    name: str = Field(min_length=1, max_length=180)
    sector_id: str
    active: bool = True
    members: list[TeamMemberIn] = []

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("Informe o nome da equipe")
        return clean

    @model_validator(mode="after")
    def _members(self) -> NotificationTeamCreateIn:
        _unique_emails(self.members)
        return self


class NotificationTeamUpdateIn(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    sector_id: str | None = None
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("Informe o nome da equipe")
        return clean

    @model_validator(mode="after")
    def _no_null(self) -> NotificationTeamUpdateIn:
        for name in ("name", "sector_id", "active"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"'{name}' não pode ser nulo")
        return self


class TeamMembersIn(CamelModel):
    """Lista completa de membros: os ausentes da lista são removidos."""

    members: list[TeamMemberIn]

    @model_validator(mode="after")
    def _members(self) -> TeamMembersIn:
        _unique_emails(self.members)
        return self

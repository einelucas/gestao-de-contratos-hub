"""Regras de situação, alerta e notificações herdadas do app de referência."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ATTENTION_DAYS = 20

# "Hoje" das regras de contrato é o dia civil em Brasília, não o do servidor
# (containers costumam rodar em UTC e virariam o dia às 21h).
CONTRACTS_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def contracts_today() -> date:
    return datetime.now(CONTRACTS_TIMEZONE).date()


def derive_situation(*, finalized: bool, end_date: date | None, today: date | None = None) -> str:
    today = today or contracts_today()
    if finalized:
        return "Finalizado"
    if end_date is None:
        return "Sem data"
    if end_date < today:
        return "Vencido"
    return "Vigente"


def derive_alert(*, situation: str, end_date: date | None, today: date | None = None) -> str:
    today = today or contracts_today()
    if situation == "Finalizado":
        return "Finalizado"
    if situation == "Sem data":
        return "SemData"
    if situation == "Vencido":
        return "Vencido"
    if end_date is not None and (end_date - today).days <= ATTENTION_DAYS:
        return "Atencao"
    return "Regular"


def days_to_end(end_date: date | None, today: date | None = None) -> int | None:
    if end_date is None:
        return None
    return (end_date - (today or contracts_today())).days

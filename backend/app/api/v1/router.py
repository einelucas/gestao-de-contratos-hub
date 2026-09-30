"""Agregador das rotas compartilhadas sob o prefixo /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, health
from app.modules.audit.router import router as audit_router
from app.modules.contract_alerts.router import router as contract_alerts_router
from app.modules.contracts.router import router as contracts_router
from app.modules.notification_teams.router import router as notification_teams_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users_router)
api_router.include_router(audit_router)
api_router.include_router(contracts_router)
api_router.include_router(contract_alerts_router)
api_router.include_router(notification_teams_router)

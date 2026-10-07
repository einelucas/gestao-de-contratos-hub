from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models.contracts import Contract, NotificationTeam, Sector, Supplier, UserSectorPermission
from app.models.user import User
from app.modules.contracts.access import (
    SectorAccess,
    assert_can_edit,
    assert_can_view,
    restrict_to_viewable,
    sector_access,
)
from app.modules.contracts.rules import contracts_today, days_to_end, derive_alert, derive_situation
from app.modules.contracts.schemas import (
    ContractCreateIn,
    ContractOut,
    ContractUpdateIn,
    ResponsibleOut,
    SectorOut,
    UserSectorPermissionOut,
    UserSectorPermissionsIn,
    UserSectorPermissionsOut,
)
from app.modules.notification_teams.service import active_recipients, load_team, recipients_problem
from app.shared.audit import record_audit


def to_contract_out(item: Contract, access: SectorAccess) -> ContractOut:
    situation = derive_situation(finalized=item.finalized, end_date=item.endDate)
    return ContractOut(
        id=item.id,
        sector_id=item.sectorId,
        sector_name=item.sector.name,
        contract_number=item.contractNumber,
        supplier_id=item.supplierId,
        supplier=item.supplier.name,
        service_description=item.serviceDescription,
        service_value=item.serviceValue,
        own_material_value=item.ownMaterialValue,
        third_party_material_value=item.thirdPartyMaterialValue,
        total_value=item.totalValue,
        start_date=item.startDate,
        end_date=item.endDate,
        unit=item.unit,
        finalized=item.finalized,
        situation=situation,
        alert=derive_alert(situation=situation, end_date=item.endDate),
        days_to_end=days_to_end(item.endDate),
        source=item.source,
        notify=item.notify,
        notify_enabled_on=item.notifyEnabledOn,
        notification_team_id=item.notificationTeamId,
        notification_team_name=item.notificationTeam.name if item.notificationTeam else None,
        notification_recipients=active_recipients(item.notificationTeam),
        notification_problem=recipients_problem(item.notificationTeam) if item.notify else None,
        notice_days=item.noticeDays,
        responsible_user_id=item.responsibleUserId,
        responsible_user_name=item.responsibleUser.name if item.responsibleUser else None,
        responsible_email=item.responsibleEmail,
        auto_renewal=item.autoRenewal,
        criticality=item.criticality,
        can_edit=access.can_edit(item.sectorId),
        created_at=item.createdAt,
        updated_at=item.updatedAt,
    )


def _contract_query() -> Select[tuple[Contract]]:
    return select(Contract).options(
        selectinload(Contract.supplier),
        selectinload(Contract.sector),
        selectinload(Contract.responsibleUser),
        selectinload(Contract.notificationTeam).selectinload(NotificationTeam.members),
    )


async def _load_contract(session: AsyncSession, contract_id: str) -> Contract:
    # populate_existing: relê colunas e relacionamentos mesmo se o objeto já estiver na sessão
    # (ex.: logo após um update), sem precisar expirar a sessão.
    stmt = _contract_query().where(Contract.id == contract_id).execution_options(populate_existing=True)
    item = (await session.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Contrato não encontrado")
    return item


def _json_safe(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _snapshot(item: Contract) -> dict[str, Any]:
    fields = (
        "serviceDescription",
        "serviceValue",
        "ownMaterialValue",
        "thirdPartyMaterialValue",
        "totalValue",
        "startDate",
        "endDate",
        "unit",
        "finalized",
        "sectorId",
        "notify",
        "notifyEnabledOn",
        "notificationTeamId",
        "autoRenewal",
        "criticality",
    )
    data = {name: _json_safe(getattr(item, name)) for name in fields}
    data["supplier"] = item.supplier.name
    return data


async def _validate_notification_team(session: AsyncSession, item: Contract) -> None:
    """Equipe precisa ser do setor do contrato; com notify=true, precisa ter destinatários ativos."""
    team: NotificationTeam | None = None
    if item.notificationTeamId:
        team = await load_team(session, item.notificationTeamId)
        if team.sectorId != item.sectorId:
            raise DomainError(
                "A equipe de notificação pertence a outro setor; selecione uma equipe do setor do contrato"
            )
    if item.notify:
        if team is None:
            raise DomainError("Para ativar os alertas, selecione a equipe de notificação do setor")
        problem = recipients_problem(team)
        if problem:
            raise DomainError(f"{problem}; ajuste a equipe antes de ativar os alertas")


def _track_notify_enabled(item: Contract, was_enabled: bool) -> None:
    """Marca o dia em que os alertas foram ligados (base da recuperação de marcos perdidos)."""
    if item.notify and not was_enabled:
        item.notifyEnabledOn = contracts_today()
    elif not item.notify:
        item.notifyEnabledOn = None


async def list_sectors(session: AsyncSession, actor: CurrentUser) -> list[SectorOut]:
    access = await sector_access(session, actor)
    counts = (
        select(Contract.sectorId, func.count(Contract.id).label("count"))
        .group_by(Contract.sectorId)
        .subquery()
    )
    stmt = (
        select(Sector, func.coalesce(counts.c.count, 0))
        .outerjoin(counts, Sector.id == counts.c.sectorId)
        .where(Sector.active.is_(True))
        .order_by(Sector.name.asc())
    )
    result = await session.execute(restrict_to_viewable(stmt, access, Sector.id))
    return [
        SectorOut(
            id=sector.id,
            slug=sector.slug,
            name=sector.name,
            acronym=sector.acronym,
            active=sector.active,
            contract_count=int(count),
            can_edit=access.can_edit(sector.id),
        )
        for sector, count in result.all()
    ]


async def list_contracts(
    session: AsyncSession, actor: CurrentUser, *, sector_id: str | None = None
) -> list[ContractOut]:
    access = await sector_access(session, actor)
    stmt = _contract_query().order_by(Contract.endDate.asc().nullslast(), Contract.contractNumber.asc())
    if sector_id:
        stmt = stmt.where(Contract.sectorId == sector_id)
    result = await session.execute(restrict_to_viewable(stmt, access))
    return [to_contract_out(item, access) for item in result.scalars().all()]


async def list_responsibles(session: AsyncSession) -> list[ResponsibleOut]:
    """Usuários ativos que podem ser vinculados como responsável de um contrato."""
    users = (
        (await session.execute(select(User).where(User.active.is_(True)).order_by(User.name.asc())))
        .scalars()
        .all()
    )
    return [ResponsibleOut(id=user.id, name=user.name, email=user.email) for user in users]


async def get_contract(session: AsyncSession, contract_id: str, actor: CurrentUser) -> ContractOut:
    access = await sector_access(session, actor)
    item = await _load_contract(session, contract_id)
    assert_can_view(access, item.sectorId)
    return to_contract_out(item, access)


async def _supplier_by_name(session: AsyncSession, name: str) -> Supplier:
    clean = " ".join(name.strip().split())
    result = await session.execute(select(Supplier).where(func.lower(Supplier.name) == clean.lower()))
    supplier = result.scalar_one_or_none()
    if supplier is None:
        supplier = Supplier(name=clean, active=True)
        session.add(supplier)
        await session.flush()
    return supplier


async def create_contract(
    session: AsyncSession, body: ContractCreateIn, current_user: CurrentUser
) -> ContractOut:
    access = await sector_access(session, current_user)
    sector = await session.get(Sector, body.sector_id)
    if sector is None or not sector.active:
        raise NotFoundError("Setor não encontrado")
    assert_can_view(access, sector.id, "Setor não encontrado")
    assert_can_edit(access, sector.id)
    exists = await session.execute(
        select(Contract.id).where(
            Contract.sectorId == body.sector_id,
            Contract.contractNumber == body.contract_number.strip(),
        )
    )
    if exists.scalar_one_or_none() is not None:
        raise ConflictError("Já existe um contrato com este número neste setor")

    supplier = await _supplier_by_name(session, body.supplier)
    calculated_total = body.service_value + body.own_material_value + body.third_party_material_value
    item = Contract(
        sectorId=body.sector_id,
        supplierId=supplier.id,
        contractNumber=body.contract_number.strip(),
        serviceDescription=body.service_description.strip(),
        serviceValue=body.service_value,
        ownMaterialValue=body.own_material_value,
        thirdPartyMaterialValue=body.third_party_material_value,
        totalValue=body.total_value if body.total_value is not None else calculated_total,
        startDate=body.start_date,
        endDate=body.end_date,
        unit=body.unit.strip(),
        finalized=body.finalized,
        notify=body.notify,
        notificationTeamId=body.notification_team_id,
        autoRenewal=body.auto_renewal,
        criticality=body.criticality,
        source="manual",
    )
    await _validate_notification_team(session, item)
    _track_notify_enabled(item, was_enabled=False)
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=current_user.id,
        action="contract.create",
        entity="Contract",
        entity_id=item.id,
        new_data={
            "contractNumber": item.contractNumber,
            "sectorId": item.sectorId,
            "notify": item.notify,
            "notificationTeamId": item.notificationTeamId,
        },
    )
    item_id = item.id
    await session.commit()
    return await get_contract(session, item_id, current_user)


_UPDATE_MAPPING = {
    "service_description": "serviceDescription",
    "service_value": "serviceValue",
    "own_material_value": "ownMaterialValue",
    "third_party_material_value": "thirdPartyMaterialValue",
    "total_value": "totalValue",
    "start_date": "startDate",
    "end_date": "endDate",
    "unit": "unit",
    "finalized": "finalized",
    "notify": "notify",
    "notification_team_id": "notificationTeamId",
    "auto_renewal": "autoRenewal",
    "criticality": "criticality",
}


async def update_contract(
    session: AsyncSession, contract_id: str, body: ContractUpdateIn, current_user: CurrentUser
) -> ContractOut:
    access = await sector_access(session, current_user)
    item = await _load_contract(session, contract_id)
    assert_can_view(access, item.sectorId)
    assert_can_edit(access, item.sectorId)

    before = _snapshot(item)
    was_enabled = item.notify
    changes = body.model_dump(exclude_unset=True)
    new_sector_id = changes.pop("sector_id", None)
    if new_sector_id and new_sector_id != item.sectorId:
        sector = await session.get(Sector, new_sector_id)
        if sector is None or not sector.active:
            raise NotFoundError("Setor não encontrado")
        assert_can_view(access, new_sector_id, "Setor não encontrado")
        assert_can_edit(access, new_sector_id)
        duplicated = await session.execute(
            select(Contract.id).where(
                Contract.sectorId == new_sector_id, Contract.contractNumber == item.contractNumber
            )
        )
        if duplicated.scalar_one_or_none() is not None:
            raise ConflictError("Já existe um contrato com este número no setor de destino")
        item.sectorId = new_sector_id
    if "supplier" in changes and changes["supplier"] is not None:
        supplier = await _supplier_by_name(session, changes.pop("supplier"))
        item.supplierId = supplier.id
    for key, value in changes.items():
        if key in _UPDATE_MAPPING:
            setattr(item, _UPDATE_MAPPING[key], value)

    # Se os componentes financeiros mudaram e total não foi enviado, recalcula.
    value_fields = {"service_value", "own_material_value", "third_party_material_value"}
    if value_fields & body.model_fields_set and "total_value" not in body.model_fields_set:
        item.totalValue = (
            Decimal(item.serviceValue)
            + Decimal(item.ownMaterialValue)
            + Decimal(item.thirdPartyMaterialValue)
        )

    await _validate_notification_team(session, item)
    _track_notify_enabled(item, was_enabled)
    await session.flush()
    await record_audit(
        session,
        user_id=current_user.id,
        action="contract.update",
        entity="Contract",
        entity_id=item.id,
        previous_data=before,
        # Chaves em camelCase, como em previous_data (`_snapshot`) e no restante da auditoria.
        new_data={
            key: _json_safe(value)
            for key, value in body.model_dump(exclude_unset=True, by_alias=True).items()
        },
    )
    item_id = item.id
    await session.commit()
    return await get_contract(session, item_id, current_user)


async def get_user_sector_permissions(session: AsyncSession, user_id: str) -> UserSectorPermissionsOut:
    if await session.get(User, user_id) is None:
        raise NotFoundError("Usuário não encontrado")
    rows = (
        await session.execute(
            select(UserSectorPermission, Sector.name)
            .join(Sector, Sector.id == UserSectorPermission.sectorId)
            .where(UserSectorPermission.userId == user_id)
            .order_by(Sector.name.asc())
        )
    ).all()
    return UserSectorPermissionsOut(
        user_id=user_id,
        items=[
            UserSectorPermissionOut(
                sector_id=permission.sectorId,
                sector_name=sector_name,
                can_view=permission.canView,
                can_edit=permission.canEdit,
            )
            for permission, sector_name in rows
        ],
    )


async def replace_user_sector_permissions(
    session: AsyncSession, user_id: str, body: UserSectorPermissionsIn, admin: CurrentUser
) -> UserSectorPermissionsOut:
    if await session.get(User, user_id) is None:
        raise NotFoundError("Usuário não encontrado")
    sector_ids = {item.sector_id for item in body.items}
    if sector_ids:
        found = set((await session.execute(select(Sector.id).where(Sector.id.in_(sector_ids)))).scalars())
        if missing := sector_ids - found:
            raise DomainError(f"Setor não encontrado: {', '.join(sorted(missing))}")

    before = (await get_user_sector_permissions(session, user_id)).model_dump(by_alias=True)["items"]
    await session.execute(delete(UserSectorPermission).where(UserSectorPermission.userId == user_id))
    for entry in body.items:
        if not entry.can_view and not entry.can_edit:
            continue
        session.add(
            UserSectorPermission(
                userId=user_id,
                sectorId=entry.sector_id,
                # Quem edita também precisa consultar o setor.
                canView=entry.can_view or entry.can_edit,
                canEdit=entry.can_edit,
            )
        )
    await session.flush()
    after = await get_user_sector_permissions(session, user_id)
    await record_audit(
        session,
        user_id=admin.id,
        action="user.sector_permissions.replace",
        entity="User",
        entity_id=user_id,
        previous_data=before,
        new_data=after.model_dump(by_alias=True)["items"],
    )
    await session.commit()
    return after

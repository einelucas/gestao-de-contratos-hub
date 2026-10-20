"""Menções e lembretes pessoais na central interna."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.common import utcnow
from app.models.contracts import Contract, InAppNotification, Sector, Supplier, UserSectorPermission
from app.models.user import User

API = "/api/v1/notificacoes-internas"


async def seed_contract(db_session) -> str:
    sector = Sector(slug="test-notifications", name="Notificações", acronym="NOT")
    supplier = Supplier(name="Fornecedor lembretes")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    contract = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="LEMB-100",
        unit="LEM",
    )
    db_session.add(contract)
    await db_session.commit()
    return contract.id


async def give_viewer_access(client, auth_header, db_session, contract_id: str) -> str:
    await client.get("/api/v1/contratos/auditoria", headers=auth_header("VIEWER"))
    viewer = (await db_session.execute(
        select(User).where(User.externalUserId == "dev:viewer")
    )).scalar_one()
    contract = (await db_session.execute(
        select(Contract).where(Contract.id == contract_id)
    )).scalar_one()
    db_session.add(UserSectorPermission(
        userId=viewer.id, sectorId=contract.sectorId, canView=True
    ))
    await db_session.commit()
    return viewer.id


async def test_mention_arrives_in_recipient_inbox_and_can_be_read(
    client, auth_header, db_session
) -> None:
    contract_id = await seed_contract(db_session)
    viewer_id = await give_viewer_access(client, auth_header, db_session, contract_id)

    published = await client.post(
        "/api/v1/contratos/" + contract_id + "/auditoria/atualizacoes",
        headers=auth_header("ADMIN"),
        data={"text": "Favor conferir @Dev Viewer", "mentionedUserIds": json.dumps([viewer_id])},
    )
    assert published.status_code == 201, published.text

    receiver = await client.get(API, headers=auth_header("VIEWER"))
    assert receiver.status_code == 200, receiver.text
    inbox = receiver.json()
    assert inbox["unreadCount"] == 1
    assert len(inbox["items"]) == 1
    assert inbox["items"][0]["kind"] == "MENTION"
    assert inbox["items"][0]["contractId"] == contract_id

    sender = await client.get(API, headers=auth_header("ADMIN"))
    assert sender.json()["unreadCount"] == 0

    notification_id = inbox["items"][0]["id"]
    cross_user = await client.patch(API + "/" + notification_id + "/lida", headers=auth_header("ADMIN"))
    assert cross_user.status_code == 404

    read = await client.patch(API + "/" + notification_id + "/lida", headers=auth_header("VIEWER"))
    assert read.status_code == 200
    assert read.json()["unreadCount"] == 0

    updated = await client.patch(
        "/api/v1/contratos/auditoria/atualizacoes/" + published.json()["id"],
        headers=auth_header("ADMIN"),
        json={"text": "Menção removida", "mentionedUserIds": []},
    )
    assert updated.status_code == 200, updated.text
    assert (await client.get(API, headers=auth_header("VIEWER"))).json()["items"] == []


async def test_personal_reminder_is_scheduled_hidden_until_due_and_private(
    client, auth_header, db_session
) -> None:
    contract_id = await seed_contract(db_session)
    await give_viewer_access(client, auth_header, db_session, contract_id)
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    response = await client.post(
        "/api/v1/contratos/" + contract_id + "/lembretes",
        headers=auth_header("VIEWER"),
        json={"message": "Cobrar retorno do fornecedor", "scheduledAt": future},
    )
    assert response.status_code == 201, response.text
    notification_id = response.json()["id"]

    hidden = await client.get(API, headers=auth_header("VIEWER"))
    assert hidden.json()["items"] == []
    assert hidden.json()["unreadCount"] == 0

    scheduled = await client.get(
        API, headers=auth_header("VIEWER"),
        params={"contractId": contract_id, "includeScheduled": True},
    )
    assert len(scheduled.json()["items"]) == 1
    assert scheduled.json()["items"][0]["kind"] == "REMINDER"

    premature = await client.patch(API + "/" + notification_id + "/lida", headers=auth_header("VIEWER"))
    assert premature.status_code == 422
    assert (await client.get(API, headers=auth_header("ADMIN"))).json()["items"] == []
    assert (await client.delete(API + "/" + notification_id, headers=auth_header("ADMIN"))).status_code == 404

    notification = (await db_session.execute(
        select(InAppNotification).where(InAppNotification.id == notification_id)
    )).scalar_one()
    notification.scheduledAt = utcnow() - timedelta(minutes=1)
    await db_session.commit()

    due = await client.get(API, headers=auth_header("VIEWER"))
    assert due.json()["unreadCount"] == 1
    assert due.json()["items"][0]["id"] == notification_id

    marked = await client.patch(API + "/" + notification_id + "/lida", headers=auth_header("VIEWER"))
    assert marked.status_code == 200
    assert marked.json()["unreadCount"] == 0

    deleted = await client.delete(API + "/" + notification_id, headers=auth_header("VIEWER"))
    assert deleted.status_code == 204
    assert (await client.get(API, headers=auth_header("VIEWER"))).json()["items"] == []


async def test_reminder_rejects_invalid_date_and_inaccessible_contract(
    client, auth_header, db_session
) -> None:
    contract_id = await seed_contract(db_session)
    invalid_date = await client.post(
        "/api/v1/contratos/" + contract_id + "/lembretes",
        headers=auth_header("ADMIN"),
        json={"message": "Test", "scheduledAt": "2026-12-15T14:30:00"},
    )
    assert invalid_date.status_code == 422
    without_access = await client.post(
        "/api/v1/contratos/" + contract_id + "/lembretes",
        headers=auth_header("VIEWER"),
        json={"message": "Test", "scheduledAt": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert without_access.status_code == 404

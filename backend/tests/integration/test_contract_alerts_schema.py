"""Restrições de banco da migration 0003_contract_alerts, contra Postgres real."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.contracts import (
    NOTICE_DAYS_NOT_APPLICABLE,
    Contract,
    ContractNotification,
    ContractNotificationType,
    Sector,
    Supplier,
)
from app.models.user import Role, User


async def _contract(db_session, **fields) -> Contract:
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor X")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    item = Contract(
        sectorId=sector.id, supplierId=supplier.id, contractNumber="100", endDate=date(2030, 1, 1), **fields
    )
    db_session.add(item)
    await db_session.commit()
    return item


def _notification(contract: Contract, **fields) -> ContractNotification:
    values = {
        "contractId": contract.id,
        "type": ContractNotificationType.ANTECEDENCIA,
        "recipient": "resp@empresa.com",
        "referenceDate": date(2030, 1, 1),
        "noticeDays": 20,
        "contractEndDate": date(2030, 1, 1),
    }
    values.update(fields)
    return ContractNotification(**values)


async def test_existing_defaults_are_safe(db_session) -> None:
    """Contrato sem configuração nunca nasce apto a disparar e-mail."""
    item = await _contract(db_session)
    row = (
        await db_session.execute(
            text(
                'SELECT notify, "noticeDays", "responsibleUserId", "responsibleEmail", "autoRenewal", '
                'criticality FROM "Contract" WHERE id = :id'
            ),
            {"id": item.id},
        )
    ).one()
    assert tuple(row) == (False, 20, None, None, False, None)


@pytest.mark.parametrize("notice_days", [0, 366, -1])
async def test_contract_notice_days_check(db_session, notice_days: int) -> None:
    item = await _contract(db_session)
    with pytest.raises(IntegrityError, match="Contract_noticeDays_check"):
        await db_session.execute(
            text('UPDATE "Contract" SET "noticeDays" = :value WHERE id = :id'),
            {"value": notice_days, "id": item.id},
        )
    await db_session.rollback()


@pytest.mark.parametrize("notice_days", [1, 365])
async def test_contract_notice_days_limits_accepted(db_session, notice_days: int) -> None:
    item = await _contract(db_session)
    await db_session.execute(
        text('UPDATE "Contract" SET "noticeDays" = :value WHERE id = :id'),
        {"value": notice_days, "id": item.id},
    )
    await db_session.commit()


async def test_notification_accepts_notice_days_not_applicable(db_session) -> None:
    item = await _contract(db_session)
    db_session.add(
        _notification(item, type=ContractNotificationType.VENCIDO, noticeDays=NOTICE_DAYS_NOT_APPLICABLE)
    )
    await db_session.commit()
    stored = (await db_session.execute(select(ContractNotification))).scalar_one()
    assert stored.noticeDays == 0
    assert stored.status.value == "PENDING"
    assert stored.attempts == 0


async def test_deleting_responsible_user_sets_null(db_session) -> None:
    user = User(name="Resp", email="resp@empresa.com", role=Role.VIEWER, active=True)
    db_session.add(user)
    await db_session.flush()
    item = await _contract(db_session, responsibleUserId=user.id, notify=True)

    await db_session.execute(text('DELETE FROM "User" WHERE id = :id'), {"id": user.id})
    await db_session.commit()

    row = (
        await db_session.execute(
            text('SELECT "responsibleUserId", notify FROM "Contract" WHERE id = :id'), {"id": item.id}
        )
    ).one()
    # O contrato continua existindo; só perde o vínculo.
    assert tuple(row) == (None, True)


async def test_deleting_contract_cascades_notifications(db_session) -> None:
    item = await _contract(db_session)
    db_session.add(_notification(item))
    await db_session.commit()

    await db_session.execute(text('DELETE FROM "Contract" WHERE id = :id'), {"id": item.id})
    await db_session.commit()

    count = (await db_session.execute(text('SELECT count(*) FROM "ContractNotification"'))).scalar_one()
    assert count == 0


async def test_dedup_key_blocks_duplicate_alert(db_session) -> None:
    item = await _contract(db_session)
    db_session.add(_notification(item))
    await db_session.commit()

    db_session.add(_notification(item))
    with pytest.raises(IntegrityError, match="ContractNotification_dedup_key"):
        await db_session.commit()
    await db_session.rollback()


async def test_dedup_key_allows_distinct_milestones(db_session) -> None:
    """60/30/20 dias, outro destinatário, outro ciclo (renovação) e outro tipo coexistem."""
    item = await _contract(db_session)
    db_session.add_all(
        [
            _notification(item, noticeDays=60),
            _notification(item, noticeDays=30),
            _notification(item, noticeDays=20),
            _notification(item, noticeDays=20, recipient="outro@empresa.com"),
            _notification(
                item, noticeDays=20, referenceDate=date(2031, 1, 1), contractEndDate=date(2031, 1, 1)
            ),
            _notification(
                item, type=ContractNotificationType.VENCIMENTO, noticeDays=NOTICE_DAYS_NOT_APPLICABLE
            ),
        ]
    )
    await db_session.commit()
    count = (await db_session.execute(text('SELECT count(*) FROM "ContractNotification"'))).scalar_one()
    assert count == 6


async def test_dedup_index_is_unique_in_database(db_session) -> None:
    row = (
        await db_session.execute(
            text(
                "SELECT i.indisunique, pg_get_indexdef(i.indexrelid) FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid WHERE c.relname = 'ContractNotification_dedup_key'"
            )
        )
    ).one()
    assert row[0] is True
    assert '("contractId", type, "referenceDate", "noticeDays", recipient)' in row[1]

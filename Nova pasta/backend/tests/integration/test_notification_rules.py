"""Régua fixa 45/20/1/0 com equipes de notificação (Etapa 7), contra Postgres real."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete, update

from app.models.contracts import (
    Contract,
    ContractNotificationStatus,
    NotificationTeam,
    NotificationTeamMember,
)
from tests.integration.test_contract_alerts import FakeAdapter, _base, _contract, _rows, _run, _team

END = date(2026, 12, 31)
MEMBERS = ["a@empresa.com", "b@empresa.com", "c@empresa.com"]


def day(days_before_end: int) -> date:
    return END - timedelta(days=days_before_end)


async def test_each_milestone_once_per_member(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", END, recipients=MEMBERS, notifyEnabledOn=day(90))
    adapter = FakeAdapter()

    # Dias de fronteira de cada janela (fora, no marco, dentro e véspera do próximo).
    for days_left in (50, 46, 45, 44, 21, 20, 19, 2, 1, 0):
        await _run(today=day(days_left), adapter=adapter)
    # Rodar de novo os dias dos marcos não duplica nada.
    for days_left in (45, 20, 1, 0):
        assert (await _run(today=day(days_left), adapter=adapter)).sent == 0

    rows = await _rows(contract_id)
    by_milestone: dict[tuple[str, int], list[str]] = {}
    for row in rows:
        by_milestone.setdefault((row.type.value, row.noticeDays), []).append(row.recipient)
    assert {key: sorted(value) for key, value in by_milestone.items()} == {
        ("ANTECEDENCIA", 45): MEMBERS,
        ("ANTECEDENCIA", 20): MEMBERS,
        ("ANTECEDENCIA", 1): MEMBERS,
        ("VENCIMENTO", 0): MEMBERS,
    }
    assert len(adapter.sent) == 12
    subjects = {m.subject for m in adapter.sent}
    assert subjects == {
        "Contrato 100 vence em 45 dias",
        "Contrato 100 vence em 20 dias",
        "Contrato 100 vence amanhã",
        "Contrato 100 vence hoje",
    }


async def test_partial_failure_retries_only_the_failed_recipient(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", END, recipients=MEMBERS, notifyEnabledOn=day(90))

    first = await _run(today=day(45), adapter=FakeAdapter(fail_recipients={"b@empresa.com"}))
    assert (first.sent, first.failed) == (2, 1)

    healthy = FakeAdapter()
    retry = await _run(today=day(44), adapter=healthy)
    assert retry.retried == 1
    assert [m.recipients for m in healthy.sent] == [["b@empresa.com"]]
    statuses = {r.recipient: (r.status, r.attempts) for r in await _rows(contract_id)}
    assert statuses == {
        "a@empresa.com": (ContractNotificationStatus.SENT, 1),
        "b@empresa.com": (ContractNotificationStatus.SENT, 2),
        "c@empresa.com": (ContractNotificationStatus.SENT, 1),
    }


async def test_new_member_is_not_notified_retroactively(db_session) -> None:
    base = await _base(db_session)
    team_id = await _team(db_session, base[0], "Equipe Obras", ["a@empresa.com"])
    contract_id = await _contract(db_session, base, "100", END, team_id=team_id, notifyEnabledOn=day(90))
    await _run(today=day(45))

    db_session.add(NotificationTeamMember(teamId=team_id, email="novo@empresa.com", active=True))
    await db_session.commit()

    # Mesmo dia e dias seguintes da janela do marco 45: o marco já foi processado.
    adapter = FakeAdapter()
    assert (await _run(today=day(45), adapter=adapter)).sent == 0
    assert (await _run(today=day(30), adapter=adapter)).sent == 0
    # Marco seguinte já inclui o novo membro.
    await _run(today=day(20), adapter=adapter)
    assert sorted(m.recipients[0] for m in adapter.sent) == ["a@empresa.com", "novo@empresa.com"]
    rows = [(r.noticeDays, r.recipient) for r in await _rows(contract_id)]
    assert (45, "novo@empresa.com") not in rows


async def test_removed_or_inactive_member_stops_receiving(db_session) -> None:
    base = await _base(db_session)
    team_id = await _team(db_session, base[0], "Equipe Obras", ["a@empresa.com", "b@empresa.com"])
    contract_id = await _contract(db_session, base, "100", END, team_id=team_id, notifyEnabledOn=day(90))
    await _run(today=day(45), adapter=FakeAdapter(fail_recipients={"b@empresa.com"}))

    await db_session.execute(
        delete(NotificationTeamMember).where(NotificationTeamMember.email == "b@empresa.com")
    )
    await db_session.commit()

    adapter = FakeAdapter()
    await _run(today=day(20), adapter=adapter)
    assert [m.recipients[0] for m in adapter.sent] == ["a@empresa.com"]
    # A falha antiga de quem saiu da equipe não é mais retentada; o histórico permanece.
    old = [r for r in await _rows(contract_id) if r.recipient == "b@empresa.com"]
    assert [(r.noticeDays, r.status) for r in old] == [(45, ContractNotificationStatus.SKIPPED)]


async def test_team_change_mid_cycle(db_session) -> None:
    base = await _base(db_session)
    team_a = await _team(db_session, base[0], "Equipe A", ["a@empresa.com"])
    team_b = await _team(db_session, base[0], "Equipe B", ["b1@empresa.com", "b2@empresa.com"])
    contract_id = await _contract(db_session, base, "100", END, team_id=team_a, notifyEnabledOn=day(90))
    await _run(today=day(45))

    await db_session.execute(
        update(Contract).where(Contract.id == contract_id).values(notificationTeamId=team_b)
    )
    await db_session.commit()

    adapter = FakeAdapter()
    assert (await _run(today=day(40), adapter=adapter)).sent == 0  # 45 não vai retroativamente para a B
    await _run(today=day(20), adapter=adapter)
    assert sorted(m.recipients[0] for m in adapter.sent) == ["b1@empresa.com", "b2@empresa.com"]
    rows = sorted((r.noticeDays, r.recipient, r.notificationTeamId) for r in await _rows(contract_id))
    assert rows == [
        (20, "b1@empresa.com", team_b),
        (20, "b2@empresa.com", team_b),
        (45, "a@empresa.com", team_a),
    ]


async def test_downtime_recovers_missed_milestone_once(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", END, notifyEnabledOn=day(90))

    adapter = FakeAdapter()
    # Job fora do ar no dia 45: volta com 44 dias e recupera o marco 45 uma única vez.
    recovered = await _run(today=day(44), adapter=adapter)
    assert [(i.notice_days, i.days_to_end) for i in recovered.items] == [(45, 44)]
    assert (await _run(today=day(43), adapter=adapter)).sent == 0
    # Fora do ar também no dia 20: volta com 19 e recupera só o 20 (o 45 não é repetido).
    await _run(today=day(19), adapter=adapter)
    assert sorted(r.noticeDays for r in await _rows(contract_id)) == [20, 45]
    assert "vence em 44 dias" in adapter.sent[0].subject


async def test_late_activation_skips_past_milestones(db_session) -> None:
    base = await _base(db_session)
    # Alertas ligados com 15 dias restantes.
    contract_id = await _contract(db_session, base, "100", END, notifyEnabledOn=day(15))

    adapter = FakeAdapter()
    for days_left in (15, 14, 10, 5, 2):
        assert (await _run(today=day(days_left), adapter=adapter)).sent == 0
    await _run(today=day(1), adapter=adapter)
    assert [(r.type.value, r.noticeDays) for r in await _rows(contract_id)] == [("ANTECEDENCIA", 1)]


async def test_inactive_or_empty_team_is_skipped_without_sending(db_session) -> None:
    base = await _base(db_session)
    inactive_team = await _team(db_session, base[0], "Equipe inativa", ["a@empresa.com"], active=False)
    inactive = await _contract(db_session, base, "100", END, team_id=inactive_team, notifyEnabledOn=day(90))
    empty = await _contract(db_session, base, "200", END, recipients=[], notifyEnabledOn=day(90))
    only_inactive_members = await _contract(db_session, base, "300", END, notifyEnabledOn=day(90))
    await db_session.execute(
        update(NotificationTeamMember)
        .where(NotificationTeamMember.email == "resp300@empresa.com")
        .values(active=False)
    )
    await db_session.commit()

    adapter = FakeAdapter()
    result = await _run(today=day(45), adapter=adapter)
    assert adapter.sent == []
    assert result.skipped == 3
    for contract_id, reason in (
        (inactive, "desativada"),
        (empty, "membros ativos"),
        (only_inactive_members, "membros ativos"),
    ):
        [row] = await _rows(contract_id)
        assert row.status == ContractNotificationStatus.SKIPPED
        assert reason in row.error


async def test_skipped_milestone_is_recovered_after_team_is_fixed(db_session) -> None:
    base = await _base(db_session)
    team_id = await _team(db_session, base[0], "Equipe Obras", [])
    contract_id = await _contract(db_session, base, "100", END, team_id=team_id, notifyEnabledOn=day(90))
    await _run(today=day(45))  # SKIPPED: sem membros

    db_session.add(NotificationTeamMember(teamId=team_id, email="a@empresa.com", active=True))
    await db_session.commit()
    adapter = FakeAdapter()
    await _run(today=day(44), adapter=adapter)
    # SKIPPED não conta como marco processado: corrigida a equipe, o 45 é recuperado dentro da janela.
    assert [m.recipients[0] for m in adapter.sent] == ["a@empresa.com"]
    statuses = sorted((r.recipient, r.status.value) for r in await _rows(contract_id))
    assert statuses == [("", "SKIPPED"), ("a@empresa.com", "SENT")]


async def test_renewal_restarts_all_milestones(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", END, notifyEnabledOn=day(90))
    for days_left in (45, 20, 1, 0):
        await _run(today=day(days_left))

    renewed = END + timedelta(days=365)
    await db_session.execute(update(Contract).where(Contract.id == contract_id).values(endDate=renewed))
    await db_session.commit()
    for days_left in (45, 20, 1, 0):
        await _run(today=renewed - timedelta(days=days_left))

    rows = await _rows(contract_id)
    assert sorted((r.contractEndDate, r.noticeDays) for r in rows) == sorted(
        [(END, n) for n in (45, 20, 1, 0)] + [(renewed, n) for n in (45, 20, 1, 0)]
    )


async def test_attention_status_is_independent_of_emails(client, auth_header, db_session) -> None:
    """Com 45 dias o primeiro e-mail sai, mas o contrato continua Regular (Atenção = 20 dias)."""
    from app.modules.contracts.rules import contracts_today

    base = await _base(db_session)
    await _contract(db_session, base, "100", contracts_today() + timedelta(days=45))
    [item] = (await client.get("/api/v1/contratos", headers=auth_header("ADMIN"))).json()["items"]
    assert item["alert"] == "Regular"
    team = await db_session.get(NotificationTeam, item["notificationTeamId"])
    assert team is not None and item["notificationRecipients"] == ["resp100@empresa.com"]

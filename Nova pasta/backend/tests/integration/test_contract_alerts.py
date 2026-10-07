"""Motor de alertas de vencimento (Etapa 2), contra Postgres real."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import select, text, update

from app.core.database import SessionLocal
from app.main import app as fastapi_app
from app.models.audit import AuditLog
from app.models.common import utcnow
from app.models.contracts import (
    Contract,
    ContractNotification,
    ContractNotificationStatus,
    ContractNotificationType,
    NotificationTeam,
    NotificationTeamMember,
    Sector,
    Supplier,
    UserSectorPermission,
)
from app.modules.contract_alerts.adapter import AlertMessage
from app.modules.contract_alerts.router import alert_adapter
from app.modules.contract_alerts.service import (
    MAX_ATTEMPTS,
    NO_RECIPIENT,
    ContractAlertService,
    preview_alerts,
)
from app.modules.contracts.rules import contracts_today

TODAY = date(2026, 10, 1)


class FakeAdapter:
    """Registra as mensagens; falha para contratos em `fail_for`, destinatários em
    `fail_recipients` (ou sempre)."""

    name = "fake"

    def __init__(
        self,
        *,
        fail_for: set[str] | None = None,
        fail_recipients: set[str] | None = None,
        fail_always: bool = False,
    ) -> None:
        self.fail_for = fail_for or set()
        self.fail_recipients = fail_recipients or set()
        self.fail_always = fail_always
        self.sent: list[AlertMessage] = []

    async def send(self, message: AlertMessage) -> None:
        if (
            self.fail_always
            or message.contract_number in self.fail_for
            or set(message.recipients) & self.fail_recipients
        ):
            raise RuntimeError("provedor indisponível")
        self.sent.append(message)


async def _base(db_session) -> tuple[str, str]:
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor X")
    db_session.add_all([sector, supplier])
    await db_session.commit()
    return sector.id, supplier.id


async def _team(db_session, sector_id: str, name: str, emails: list[str], *, active: bool = True) -> str:
    team = NotificationTeam(name=name, sectorId=sector_id, active=active)
    team.members = [NotificationTeamMember(email=email, active=True) for email in emails]
    db_session.add(team)
    await db_session.commit()
    return team.id


async def _contract(
    db_session,
    base: tuple[str, str],
    number: str,
    end: date | None,
    *,
    recipients: list[str] | None = None,
    team_id: str | None = None,
    with_team: bool = True,
    **fields,
) -> str:
    """Contrato com notify=true e uma equipe própria no setor (padrão: um membro resp<número>@empresa.com)."""
    if with_team and team_id is None:
        emails = [f"resp{number}@empresa.com"] if recipients is None else recipients
        team_id = await _team(db_session, base[0], f"Equipe {number}", emails)
    values = {"notify": True, "notificationTeamId": team_id}
    values.update(fields)
    item = Contract(sectorId=base[0], supplierId=base[1], contractNumber=number, endDate=end, **values)
    db_session.add(item)
    await db_session.commit()
    return item.id


async def _run(today: date = TODAY, adapter: FakeAdapter | None = None, dry_run: bool = False):
    async with SessionLocal() as session:
        return await ContractAlertService(session, adapter or FakeAdapter()).run(today=today, dry_run=dry_run)


async def _rows(contract_id: str | None = None) -> list[ContractNotification]:
    async with SessionLocal() as session:
        stmt = select(ContractNotification).order_by(ContractNotification.createdAt, ContractNotification.id)
        if contract_id:
            stmt = stmt.where(ContractNotification.contractId == contract_id)
        return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------- elegibilidade


async def test_antecedencia_sent_once_per_cycle(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    adapter = FakeAdapter()

    first = await _run(adapter=adapter)
    assert (first.contracts_analyzed, first.eligible, first.sent, first.duplicates) == (1, 1, 1, 0)
    item = first.items[0]
    assert item.action == "sent"
    assert item.type == ContractNotificationType.ANTECEDENCIA
    assert item.days_to_end == 20
    assert item.recipient == "resp100@empresa.com"

    [row] = await _rows(contract_id)
    assert row.status == ContractNotificationStatus.SENT
    assert (row.type, row.referenceDate, row.noticeDays, row.contractEndDate) == (
        ContractNotificationType.ANTECEDENCIA,
        TODAY + timedelta(days=20),
        20,
        TODAY + timedelta(days=20),
    )
    assert (
        row.attempts == 1 and row.sentAt is not None and row.lastAttemptAt is not None and row.error is None
    )

    [message] = adapter.sent
    assert message.recipients == ["resp100@empresa.com"]
    assert message.contract_number == "100" and message.supplier == "Fornecedor X"
    assert "vence em 20 dias" in message.subject

    # Rodar de novo no mesmo dia não reenvia.
    second = await _run(adapter=adapter)
    assert (second.sent, second.duplicates) == (0, 1)
    assert second.items[0].action == "already_notified"
    assert len(adapter.sent) == 1
    assert len(await _rows(contract_id)) == 1


async def test_fixed_schedule_milestones(db_session) -> None:
    base = await _base(db_session)
    for number, days in (("045", 45), ("020", 20), ("001", 1), ("000", 0), ("060", 60), ("030", 30)):
        await _contract(db_session, base, number, TODAY + timedelta(days=days), notifyEnabledOn=TODAY)

    result = await _run()
    assert result.contracts_analyzed == 6
    got = sorted((i.contract_number, i.type.value, i.notice_days) for i in result.items)
    # 60 dias: fora da régua. 30 dias: marco 45 já passou antes de ligar os alertas (hoje).
    assert got == [
        ("000", "VENCIMENTO", 0),
        ("001", "ANTECEDENCIA", 1),
        ("020", "ANTECEDENCIA", 20),
        ("045", "ANTECEDENCIA", 45),
    ]


async def test_vencimento_uses_notice_days_not_applicable(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY)

    result = await _run()
    assert result.items[0].type == ContractNotificationType.VENCIMENTO
    [row] = await _rows(contract_id)
    assert (row.referenceDate, row.noticeDays, row.status) == (TODAY, 0, ContractNotificationStatus.SENT)


async def test_vencido_every_seven_days(db_session) -> None:
    base = await _base(db_session)
    end = TODAY - timedelta(days=7)
    contract_id = await _contract(db_session, base, "100", end)
    adapter = FakeAdapter()

    sent_on = {}
    for overdue in range(7, 22):
        result = await _run(today=end + timedelta(days=overdue), adapter=adapter)
        sent_on[overdue] = result.sent
    # 7, 14 e 21 dias; nunca 8, 9, 10…
    assert [days for days, sent in sent_on.items() if sent] == [7, 14, 21]

    rows = await _rows(contract_id)
    assert [r.referenceDate for r in rows] == [end + timedelta(days=d) for d in (7, 14, 21)]
    assert all(r.type == ContractNotificationType.VENCIDO and r.noticeDays == 0 for r in rows)
    assert all(r.contractEndDate == end for r in rows)
    assert "vencido há 14 dias" in adapter.sent[1].subject


async def test_ineligible_contracts_are_ignored(db_session) -> None:
    base = await _base(db_session)
    await _contract(db_session, base, "100", TODAY + timedelta(days=20), notify=False)
    await _contract(db_session, base, "200", TODAY + timedelta(days=20), finalized=True)
    await _contract(db_session, base, "300", None)
    await _contract(db_session, base, "400", TODAY - timedelta(days=7), finalized=True)

    result = await _run()
    # Só entram na análise os contratos com notify=true e não finalizados.
    assert (result.contracts_analyzed, result.eligible, result.sent) == (1, 0, 0)
    assert await _rows() == []


async def test_renewal_opens_new_cycle_and_keeps_history(db_session) -> None:
    base = await _base(db_session)
    first_end = TODAY + timedelta(days=20)
    contract_id = await _contract(db_session, base, "100", first_end)
    await _run()

    renewed_end = first_end + timedelta(days=365)
    await db_session.execute(update(Contract).where(Contract.id == contract_id).values(endDate=renewed_end))
    await db_session.commit()

    # Dias do ciclo antigo não geram mais nada.
    assert (await _run(today=first_end)).eligible == 0

    result = await _run(today=renewed_end - timedelta(days=20))
    assert result.sent == 1
    rows = await _rows(contract_id)
    assert [(r.referenceDate, r.contractEndDate) for r in rows] == [
        (first_end, first_end),
        (renewed_end, renewed_end),
    ]


# ---------------------------------------------------------------- destinatário


async def test_team_members_are_the_recipients(db_session) -> None:
    base = await _base(db_session)
    end = TODAY + timedelta(days=20)
    team_id = await _team(
        db_session, base[0], "Equipe Obras", ["a@empresa.com", "b@empresa.com", "c@empresa.com"]
    )
    await db_session.execute(
        update(NotificationTeamMember)
        .where(NotificationTeamMember.email == "c@empresa.com")
        .values(active=False)
    )
    await db_session.commit()
    contract_id = await _contract(db_session, base, "100", end, team_id=team_id)

    adapter = FakeAdapter()
    result = await _run(adapter=adapter)
    # Um e-mail por membro ativo, sem expor os demais destinatários.
    assert sorted(m.recipients[0] for m in adapter.sent) == ["a@empresa.com", "b@empresa.com"]
    assert all(len(m.recipients) == 1 for m in adapter.sent)
    assert result.sent == 2
    rows = await _rows(contract_id)
    assert sorted(r.recipient for r in rows) == ["a@empresa.com", "b@empresa.com"]
    assert all(r.notificationTeamId == team_id for r in rows)


async def test_missing_recipient_is_skipped_and_traceable(db_session) -> None:
    base = await _base(db_session)
    # notify=true sem destinatário só é possível por fora da API (validação 422 lá).
    no_recipient = await _contract(db_session, base, "100", TODAY + timedelta(days=20), recipients=[])
    ok = await _contract(db_session, base, "200", TODAY + timedelta(days=20))

    result = await _run()
    assert (result.sent, result.skipped) == (1, 1)
    [row] = await _rows(no_recipient)
    assert row.status == ContractNotificationStatus.SKIPPED
    assert row.recipient == NO_RECIPIENT
    assert "membros ativos" in row.error
    assert (await _rows(ok))[0].status == ContractNotificationStatus.SENT

    # O skip também é deduplicado: não gera uma linha nova a cada execução.
    again = await _run()
    assert (again.skipped, again.duplicates) == (0, 2)
    assert len(await _rows(no_recipient)) == 1


# ---------------------------------------------------------------- falhas e retry


async def test_failure_in_one_contract_does_not_stop_others(db_session) -> None:
    base = await _base(db_session)
    failing = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    ok = await _contract(db_session, base, "200", TODAY + timedelta(days=20))

    result = await _run(adapter=FakeAdapter(fail_for={"100"}))
    assert (result.sent, result.failed) == (1, 1)
    [failed_row] = await _rows(failing)
    assert failed_row.status == ContractNotificationStatus.FAILED
    assert failed_row.attempts == 1
    assert "provedor indisponível" in failed_row.error
    assert failed_row.sentAt is None
    assert (await _rows(ok))[0].status == ContractNotificationStatus.SENT


async def test_retry_reuses_row_until_limit(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    broken = FakeAdapter(fail_always=True)

    first = await _run(adapter=broken)
    assert first.failed == 1 and first.retried == 0  # falha desta execução não é retentada nela mesma

    for expected_attempts in (2, 3):
        result = await _run(adapter=broken)
        assert result.retried == 1 and result.failed == 1
        [row] = await _rows(contract_id)
        assert row.attempts == expected_attempts
        assert row.status == ContractNotificationStatus.FAILED

    # Atingiu o limite: nem com o provedor de volta há nova tentativa automática.
    healthy = FakeAdapter()
    after_limit = await _run(adapter=healthy)
    assert after_limit.retried == 0
    assert healthy.sent == []
    [row] = await _rows(contract_id)
    assert (row.attempts, row.status) == (MAX_ATTEMPTS, ContractNotificationStatus.FAILED)


async def test_retry_success_clears_error(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _run(adapter=FakeAdapter(fail_always=True))

    # Dia seguinte: o marco de 20 dias ainda está na janela de recuperação (conta como
    # elegível), mas já foi processado — só o retry envia, uma única vez.
    healthy = FakeAdapter()
    result = await _run(today=TODAY + timedelta(days=1), adapter=healthy)
    assert (result.eligible, result.retried, result.sent) == (1, 1, 1)
    assert len(healthy.sent) == 1
    assert healthy.sent[0].days_to_end == 19

    [row] = await _rows(contract_id)
    assert row.status == ContractNotificationStatus.SENT
    assert (row.attempts, row.error) == (2, None)
    assert row.sentAt is not None


async def test_retry_skipped_when_contract_no_longer_eligible(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _run(adapter=FakeAdapter(fail_always=True))

    await db_session.execute(update(Contract).where(Contract.id == contract_id).values(finalized=True))
    await db_session.commit()

    healthy = FakeAdapter()
    result = await _run(adapter=healthy)
    assert result.skipped == 1 and healthy.sent == []
    [row] = await _rows(contract_id)
    assert row.status == ContractNotificationStatus.SKIPPED


async def test_stale_pending_is_recovered_and_retried(db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _run()
    # Simula um processo que morreu entre reivindicar a linha e gravar o resultado.
    await db_session.execute(
        update(ContractNotification)
        .where(ContractNotification.contractId == contract_id)
        .values(
            status=ContractNotificationStatus.PENDING,
            sentAt=None,
            lastAttemptAt=utcnow() - timedelta(hours=1),
        )
    )
    await db_session.commit()

    result = await _run()
    assert result.retried == 1
    [row] = await _rows(contract_id)
    assert (row.status, row.attempts) == (ContractNotificationStatus.SENT, 2)


async def test_concurrent_runs_send_once(db_session) -> None:
    base = await _base(db_session)
    for number in ("100", "200", "300"):
        await _contract(db_session, base, number, TODAY + timedelta(days=20))
    first, second = FakeAdapter(), FakeAdapter()

    results = await asyncio.gather(_run(adapter=first), _run(adapter=second))
    assert len(first.sent) + len(second.sent) == 3
    assert sum(r.sent for r in results) == 3
    assert sum(r.duplicates for r in results) == 3
    assert len(await _rows()) == 3


# ---------------------------------------------------------------- dry-run


async def test_dry_run_has_no_side_effects(db_session) -> None:
    base = await _base(db_session)
    new_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20), autoRenewal=True)
    await _contract(db_session, base, "200", TODAY + timedelta(days=20))
    await _run(adapter=FakeAdapter(fail_for={"200"}))  # 100 SENT, 200 FAILED
    # Remove o histórico do 100 para que ele volte a ser "novo" na prévia.
    await db_session.execute(
        text('DELETE FROM "ContractNotification" WHERE "contractId" = :id'), {"id": new_id}
    )
    await db_session.commit()
    before = [(r.id, r.status, r.attempts, r.updatedAt) for r in await _rows()]

    preview = await preview_alerts(TODAY)
    assert preview.dry_run is True and preview.provider is None
    by_contract = {(i.contract_number, i.retry): i for i in preview.items}
    would_send = by_contract[("100", False)]
    assert would_send.action == "would_send"
    assert would_send.recipient == "resp100@empresa.com"
    assert would_send.contract_end_date == TODAY + timedelta(days=20)
    assert would_send.days_to_end == 20
    assert would_send.reason == "Marco de 20 dias antes do vencimento"
    assert by_contract[("200", False)].action == "already_notified"
    assert by_contract[("200", True)].action == "would_retry"

    after = [(r.id, r.status, r.attempts, r.updatedAt) for r in await _rows()]
    assert after == before


async def test_auto_renewal_is_highlighted(db_session) -> None:
    base = await _base(db_session)
    await _contract(db_session, base, "100", TODAY + timedelta(days=20), autoRenewal=True)
    await _contract(db_session, base, "200", TODAY + timedelta(days=20), autoRenewal=False)
    adapter = FakeAdapter()
    await _run(adapter=adapter)
    bodies = {m.contract_number: m.body for m in adapter.sent}
    assert "Este contrato possui renovação automática." in bodies["100"]
    assert "renovação automática" not in bodies["200"]


# ---------------------------------------------------------------- endpoints


@pytest.fixture
def fake_adapter():
    adapter = FakeAdapter()
    fastapi_app.dependency_overrides[alert_adapter] = lambda: adapter
    yield adapter
    fastapi_app.dependency_overrides.pop(alert_adapter, None)


async def test_alert_endpoints_require_admin(client, auth_header) -> None:
    for method, url in (
        ("get", "/api/v1/alertas/previa"),
        ("post", "/api/v1/alertas/executar"),
        ("get", "/api/v1/notificacoes-contratos"),
        ("post", "/api/v1/notificacoes-contratos/qualquer/reenviar"),
    ):
        response = await client.request(method.upper(), url, headers=auth_header("ANALYST"))
        assert response.status_code == 403, url


async def test_preview_and_execute_endpoints(client, auth_header, db_session, fake_adapter) -> None:
    base = await _base(db_session)
    today = contracts_today()
    await _contract(db_session, base, "100", today + timedelta(days=20))

    preview = await client.get("/api/v1/alertas/previa", headers=auth_header("ADMIN"))
    assert preview.status_code == 200
    assert preview.json()["dryRun"] is True
    assert preview.json()["items"][0]["action"] == "would_send"

    simulated = await client.get(
        f"/api/v1/alertas/previa?data={(today + timedelta(days=20)).isoformat()}",
        headers=auth_header("ADMIN"),
    )
    assert simulated.json()["items"][0]["type"] == "VENCIMENTO"

    default_is_dry = await client.post("/api/v1/alertas/executar", headers=auth_header("ADMIN"))
    assert default_is_dry.json()["dryRun"] is True
    assert await _rows() == []

    with_date = await client.post(
        f"/api/v1/alertas/executar?dry_run=false&data={today.isoformat()}", headers=auth_header("ADMIN")
    )
    assert with_date.status_code == 422

    real = await client.post("/api/v1/alertas/executar?dry_run=false", headers=auth_header("ADMIN"))
    assert real.status_code == 200
    assert real.json()["sent"] == 1 and real.json()["provider"] == "fake"
    assert len(fake_adapter.sent) == 1

    [entry] = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "contract_alerts.run")))
        .scalars()
        .all()
    )
    assert entry.metadata_["trigger"] == "manual"
    assert entry.metadata_["sent"] == 1


async def test_resend_endpoint(client, auth_header, db_session, fake_adapter) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _run(adapter=FakeAdapter(fail_always=True))
    [row] = await _rows(contract_id)

    resent = await client.post(
        f"/api/v1/notificacoes-contratos/{row.id}/reenviar", headers=auth_header("ADMIN")
    )
    assert resent.status_code == 200
    body = resent.json()
    assert (body["id"], body["status"], body["attempts"], body["error"]) == (row.id, "SENT", 2, None)
    assert len(await _rows(contract_id)) == 1

    not_failed = await client.post(
        f"/api/v1/notificacoes-contratos/{row.id}/reenviar", headers=auth_header("ADMIN")
    )
    assert not_failed.status_code == 409

    missing = await client.post(
        "/api/v1/notificacoes-contratos/nao-existe/reenviar", headers=auth_header("ADMIN")
    )
    assert missing.status_code == 404

    [entry] = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "contract_notification.resend")))
        .scalars()
        .all()
    )
    assert entry.entityId == row.id
    assert entry.previousData == {
        "status": "FAILED",
        "attempts": 1,
        "error": "RuntimeError: provedor indisponível",
    }
    assert entry.newData == {"status": "SENT", "attempts": 2, "error": None}


async def test_resend_respects_attempt_limit(client, auth_header, db_session, fake_adapter) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _run(adapter=FakeAdapter(fail_always=True))
    await db_session.execute(
        update(ContractNotification)
        .where(ContractNotification.contractId == contract_id)
        .values(attempts=MAX_ATTEMPTS)
    )
    await db_session.commit()
    [row] = await _rows(contract_id)

    response = await client.post(
        f"/api/v1/notificacoes-contratos/{row.id}/reenviar", headers=auth_header("ADMIN")
    )
    assert response.status_code == 409
    assert fake_adapter.sent == []


async def test_contract_notifications_respect_sector_access(client, auth_header, db_session) -> None:
    base = await _base(db_session)
    contract_id = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _run()
    url = f"/api/v1/contratos/{contract_id}/notificacoes"

    hidden = await client.get(url, headers=auth_header("VIEWER"))
    assert hidden.status_code == 404

    viewer_id = (await client.get("/api/v1/auth/me", headers=auth_header("VIEWER"))).json()["id"]
    db_session.add(UserSectorPermission(userId=viewer_id, sectorId=base[0], canView=True))
    await db_session.commit()

    visible = await client.get(url, headers=auth_header("VIEWER"))
    assert visible.status_code == 200
    [item] = visible.json()["items"]
    assert (item["contractNumber"], item["status"], item["canRetry"]) == ("100", "SENT", False)


async def test_admin_notification_list_filters(client, auth_header, db_session) -> None:
    base = await _base(db_session)
    first = await _contract(db_session, base, "100", TODAY + timedelta(days=20))
    await _contract(db_session, base, "200", TODAY)
    await _run(adapter=FakeAdapter(fail_for={"200"}))
    url = "/api/v1/notificacoes-contratos"
    admin = auth_header("ADMIN")

    everything = (await client.get(url, headers=admin)).json()
    assert everything["pagination"]["total"] == 2

    failed = (await client.get(f"{url}?status=FAILED", headers=admin)).json()
    assert [i["contractNumber"] for i in failed["items"]] == ["200"]
    assert failed["items"][0]["canRetry"] is True

    by_type = (await client.get(f"{url}?tipo=ANTECEDENCIA", headers=admin)).json()
    assert [i["contractNumber"] for i in by_type["items"]] == ["100"]

    by_contract = (await client.get(f"{url}?contractId={first}", headers=admin)).json()
    assert by_contract["pagination"]["total"] == 1

    by_recipient = (await client.get(f"{url}?destinatario=RESP200", headers=admin)).json()
    assert [i["contractNumber"] for i in by_recipient["items"]] == ["200"]

    today_utc = utcnow().date()
    in_period = (await client.get(f"{url}?de={today_utc}&ate={today_utc}", headers=admin)).json()
    assert in_period["pagination"]["total"] == 2
    out_of_period = (await client.get(f"{url}?ate={today_utc - timedelta(days=1)}", headers=admin)).json()
    assert out_of_period["pagination"]["total"] == 0

    paged = (await client.get(f"{url}?pageSize=1&page=2", headers=admin)).json()
    assert len(paged["items"]) == 1
    assert paged["pagination"] == {"page": 2, "pageSize": 1, "total": 2, "totalPages": 2}


# ---------------------------------------------------------------- job


def test_job_dry_run_cli(capsys) -> None:
    from app.jobs.contract_alerts import main

    assert main(["--dry-run", "--date", "2026-10-01"]) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "contratos analisados" in out


def test_job_refuses_date_override_in_production(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.jobs.contract_alerts import main

    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert main(["--date", "2026-10-01"]) == 2

"""Modelo do e-mail de alerta (`GET /alertas/modelo`), contra Postgres real."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit import AuditLog
from app.models.contracts import (
    Contract,
    ContractCriticality,
    ContractNotification,
    Sector,
    UserSectorPermission,
)
from app.modules.contracts.rules import contracts_today
from tests.integration.test_contract_alerts import (  # noqa: F401
    TODAY,
    FakeAdapter,
    _base,
    _contract,
    _run,
    _team,
    fake_adapter,
)

MEMBERS = ["a@empresa.com", "b@empresa.com", "c@empresa.com"]


async def _preview(
    client, auth_header, contract_id: str, tipo: str = "ANTECEDENCIA", role: str = "ADMIN", **params
):
    query = "&".join(
        f"{key}={value}" for key, value in {"contrato": contract_id, "tipo": tipo, **params}.items()
    )
    return await client.get(f"/api/v1/alertas/modelo?{query}", headers=auth_header(role))


async def test_email_preview_all_milestones(client, auth_header, db_session) -> None:
    base = await _base(db_session)
    today = contracts_today()
    future = await _contract(db_session, base, "100", today + timedelta(days=90), recipients=MEMBERS)
    overdue = await _contract(db_session, base, "200", today - timedelta(days=10))

    expected = {
        ("ANTECEDENCIA", 45): "Contrato 100 vence em 45 dias",
        ("ANTECEDENCIA", 20): "Contrato 100 vence em 20 dias",
        ("ANTECEDENCIA", 1): "Contrato 100 vence amanhã",
        ("VENCIMENTO", None): "Contrato 100 vence hoje",
    }
    for (tipo, dias), subject in expected.items():
        params = {"dias": dias} if dias else {}
        body = (await _preview(client, auth_header, future, tipo, **params)).json()
        assert body["subject"] == subject
        assert body["noticeDays"] == (dias or 0)
        assert body["actualDaysToEnd"] == 90

    # Vencido: atraso real quando já venceu; 7 dias como exemplo quando ainda não venceu.
    assert (await _preview(client, auth_header, overdue, "VENCIDO")).json()[
        "subject"
    ] == "Contrato 200 está vencido há 10 dias"
    assert (await _preview(client, auth_header, future, "VENCIDO")).json()["daysToEnd"] == -7

    # Data simulada: os dias passam a ser os reais daquele dia.
    simulated = (
        await _preview(
            client,
            auth_header,
            future,
            "ANTECEDENCIA",
            dias=45,
            data=(today + timedelta(days=46)).isoformat(),
        )
    ).json()
    assert simulated["daysToEnd"] == 44
    assert simulated["endDate"] == (today + timedelta(days=90)).isoformat()

    # Marco fora da régua é recusado.
    assert (await _preview(client, auth_header, future, "ANTECEDENCIA", dias=30)).status_code == 422


async def test_email_preview_team_and_flags(client, auth_header, db_session) -> None:
    base = await _base(db_session)
    today = contracts_today()
    disabled = await _contract(
        db_session, base, "100", today + timedelta(days=20), recipients=[], notify=False
    )
    rich = await _contract(
        db_session,
        base,
        "200",
        today + timedelta(days=20),
        recipients=MEMBERS,
        autoRenewal=True,
        criticality=ContractCriticality.ALTA,
        serviceDescription='<img src=x onerror=alert(1)> & "Ç"',
    )
    no_team = await _contract(db_session, base, "300", None, with_team=False, notify=False)

    body = (await _preview(client, auth_header, disabled)).json()
    assert body["notify"] is False
    assert body["recipients"] == []
    assert "membros ativos" in body["recipientsProblem"]

    body = (await _preview(client, auth_header, rich)).json()
    assert body["teamName"] == "Equipe 200"
    assert body["recipients"] == MEMBERS
    assert body["recipientsProblem"] is None
    assert "Este contrato possui renovação automática." in body["html"]
    assert "Este contrato possui renovação automática." in body["text"]
    assert "Alta" in body["html"]
    assert "<img src=x" not in body["html"]
    assert "&lt;img src=x onerror=alert(1)&gt; &amp; &quot;Ç&quot;" in body["html"]
    assert "a@empresa.com" not in body["html"]  # o corpo não expõe destinatários

    body = (await _preview(client, auth_header, no_team)).json()
    assert body["teamName"] is None and body["recipients"] == []
    assert body["illustrativeDate"] is True and body["actualDaysToEnd"] is None


async def test_email_preview_is_the_same_as_real_send(client, auth_header, db_session) -> None:
    """Prévia e envio real usam o mesmo builder: assunto, HTML e texto idênticos para cada membro."""
    base = await _base(db_session)
    today = contracts_today()
    contract_id = await _contract(
        db_session,
        base,
        "100",
        today + timedelta(days=20),
        recipients=MEMBERS,
        autoRenewal=True,
        criticality=ContractCriticality.MEDIA,
    )
    adapter = FakeAdapter()
    await _run(today=today, adapter=adapter)
    assert len(adapter.sent) == 3

    preview = (await _preview(client, auth_header, contract_id, dias=20, data=today.isoformat())).json()
    for sent in adapter.sent:
        assert preview["subject"] == sent.subject
        assert preview["html"] == sent.html_body
        assert preview["text"] == sent.body
    assert sorted(m.recipients[0] for m in adapter.sent) == preview["recipients"]


@pytest.mark.parametrize("role", ["VIEWER", "ANALYST"])
async def test_email_preview_respects_sector_permissions(client, auth_header, db_session, role: str) -> None:
    base = await _base(db_session)
    other = Sector(slug="ti", name="TI", acronym="TI")
    db_session.add(other)
    await db_session.commit()
    secret_team = await _team(db_session, other.id, "Equipe TI", ["segredo@empresa.com"])
    secret = await _contract(
        db_session, (other.id, base[1]), "999", TODAY + timedelta(days=20), team_id=secret_team
    )
    visible = await _contract(db_session, base, "100", TODAY + timedelta(days=20))

    user_id = (await client.get("/api/v1/auth/me", headers=auth_header(role))).json()["id"]
    assert (await _preview(client, auth_header, visible, role=role)).status_code == 404

    db_session.add(UserSectorPermission(userId=user_id, sectorId=base[0], canView=True))
    await db_session.commit()
    assert (await _preview(client, auth_header, visible, role=role)).status_code == 200

    hidden = await _preview(client, auth_header, secret, role=role)
    assert hidden.status_code == 404
    for leaked in ("999", "Fornecedor X", "segredo@empresa.com", "Equipe TI", "vence"):
        assert leaked not in hidden.text

    missing = await _preview(client, auth_header, "nao-existe", role=role)
    assert missing.status_code == 404
    # Mesma resposta de "inexistente": não revela que o contrato existe.
    assert missing.json() == hidden.json()


async def test_email_preview_has_no_side_effects(client, auth_header, db_session, fake_adapter) -> None:  # noqa: F811
    base = await _base(db_session)
    today = contracts_today()
    contract_id = await _contract(db_session, base, "100", today + timedelta(days=20), recipients=MEMBERS)
    await _run(today=today, adapter=FakeAdapter(fail_recipients={"b@empresa.com"}))

    async def snapshot():
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(
                        ContractNotification.id,
                        ContractNotification.status,
                        ContractNotification.attempts,
                        ContractNotification.sentAt,
                        ContractNotification.updatedAt,
                    ).order_by(ContractNotification.id)
                )
            ).all()
            contract = (
                await session.execute(
                    select(
                        Contract.updatedAt, Contract.notify, Contract.endDate, Contract.notificationTeamId
                    ).where(Contract.id == contract_id)
                )
            ).one()
            audits = (await session.execute(select(AuditLog.id))).scalars().all()
            return [tuple(row) for row in rows], tuple(contract), len(audits)

    before = await snapshot()
    assert len(before[0]) == 3
    for tipo, dias in (
        ("ANTECEDENCIA", 45),
        ("ANTECEDENCIA", 20),
        ("ANTECEDENCIA", 1),
        ("VENCIMENTO", None),
        ("VENCIDO", None),
    ):
        params = {"dias": dias} if dias else {}
        assert (await _preview(client, auth_header, contract_id, tipo, **params)).status_code == 200
        assert (
            await _preview(client, auth_header, contract_id, tipo, data=today.isoformat(), **params)
        ).status_code == 200
    after = await snapshot()

    assert after == before
    assert fake_adapter.sent == []

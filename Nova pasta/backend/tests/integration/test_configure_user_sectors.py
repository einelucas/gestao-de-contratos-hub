"""Script administrativo scripts/configure_user_sectors.py, contra Postgres real."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.contracts import Sector, UserSectorPermission
from app.models.user import Role, User
from scripts.configure_user_sectors import (
    AUDIT_ACTION,
    ConfigError,
    Grant,
    all_sector_grants,
    apply_grants,
    grants_from_csv,
    main,
)


async def _setup(db_session) -> None:
    db_session.add_all(
        [
            Sector(slug="obras", name="Obras", acronym="OBR"),
            Sector(slug="ti", name="TI", acronym="TI"),
            Sector(slug="antigo", name="Antigo", acronym="ANT", active=False),
            User(name="Ana", email="ana@empresa.com", role=Role.ANALYST, active=True),
            User(name="Vera", email="vera@empresa.com", role=Role.VIEWER, active=True),
            User(name="Adm", email="adm@empresa.com", role=Role.ADMIN, active=True),
            User(name="Ina", email="ina@empresa.com", role=Role.ANALYST, active=False),
        ]
    )
    await db_session.commit()


async def _permissions(db_session) -> list[tuple[str, str, bool, bool]]:
    rows = (
        await db_session.execute(
            select(User.email, Sector.slug, UserSectorPermission.canView, UserSectorPermission.canEdit)
            .join(User, User.id == UserSectorPermission.userId)
            .join(Sector, Sector.id == UserSectorPermission.sectorId)
            .order_by(User.email, Sector.slug)
        )
    ).all()
    return [tuple(row) for row in rows]


async def _audit_count(db_session) -> int:
    return (
        await db_session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == AUDIT_ACTION)
        )
    ).scalar_one()


async def test_grant_is_idempotent_and_audited(db_session) -> None:
    await _setup(db_session)

    first = await apply_grants(db_session, [Grant(user="ANA@empresa.com", sector="obras")])
    assert first[0].startswith("criado")
    second = await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="obras")])
    assert second[0].startswith("sem mudança")

    assert await _permissions(db_session) == [("ana@empresa.com", "obras", True, False)]
    # Só a mudança real gera auditoria.
    assert await _audit_count(db_session) == 1


async def test_upgrade_to_edit_and_revoke(db_session) -> None:
    await _setup(db_session)
    await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="obras")])

    changed = await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="obras", can_edit=True)])
    assert changed[0].startswith("alterado")
    assert await _permissions(db_session) == [("ana@empresa.com", "obras", True, True)]

    revoked = await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="obras", revoke=True)])
    assert revoked[0].startswith("revogado")
    assert await _permissions(db_session) == []

    entries = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == AUDIT_ACTION).order_by(AuditLog.createdAt)
            )
        )
        .scalars()
        .all()
    )
    assert [e.newData["permission"] for e in entries] == [
        {"canView": True, "canEdit": False},
        {"canView": True, "canEdit": True},
        None,
    ]
    assert entries[1].previousData["permission"] == {"canView": True, "canEdit": False}


async def test_grant_does_not_touch_other_sectors(db_session) -> None:
    await _setup(db_session)
    await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="obras")])
    await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="ti", can_edit=True)])
    assert await _permissions(db_session) == [
        ("ana@empresa.com", "obras", True, False),
        ("ana@empresa.com", "ti", True, True),
    ]


async def test_admin_is_skipped(db_session) -> None:
    await _setup(db_session)
    report = await apply_grants(db_session, [Grant(user="adm@empresa.com", sector="obras", can_edit=True)])
    assert report[0].startswith("ignorado")
    assert await _permissions(db_session) == []


async def test_viewer_can_edit_flag_is_stored_with_warning(db_session) -> None:
    await _setup(db_session)
    report = await apply_grants(db_session, [Grant(user="vera@empresa.com", sector="obras", can_edit=True)])
    assert "VIEWER nunca edita" in report[0]


async def test_errors_roll_back_the_whole_batch(db_session) -> None:
    await _setup(db_session)

    with pytest.raises(ConfigError, match="inativo"):
        await apply_grants(db_session, [Grant(user="ina@empresa.com", sector="obras")])

    with pytest.raises(ConfigError, match="Setor não encontrado"):
        await apply_grants(
            db_session,
            [
                Grant(user="ana@empresa.com", sector="obras"),
                Grant(user="ana@empresa.com", sector="nao-existe"),
            ],
        )

    with pytest.raises(ConfigError, match="Usuário não encontrado"):
        await apply_grants(db_session, [Grant(user="ninguem@empresa.com", sector="obras")])

    assert await _permissions(db_session) == []
    assert await _audit_count(db_session) == 0


async def test_dry_run_writes_nothing(db_session) -> None:
    await _setup(db_session)
    report = await apply_grants(db_session, [Grant(user="ana@empresa.com", sector="obras")], dry_run=True)
    assert report[0].startswith("criado")
    assert await _permissions(db_session) == []
    assert await _audit_count(db_session) == 0


async def test_all_sectors_blocked_outside_dev(db_session) -> None:
    await _setup(db_session)
    for env in ("production", "staging"):
        with pytest.raises(ConfigError, match="development/test"):
            await all_sector_grants(db_session, "ana@empresa.com", can_edit=False, app_env=env)

    grants = await all_sector_grants(db_session, "ana@empresa.com", can_edit=False, app_env="development")
    await apply_grants(db_session, grants)
    # Só setores ativos.
    assert await _permissions(db_session) == [
        ("ana@empresa.com", "obras", True, False),
        ("ana@empresa.com", "ti", True, False),
    ]


def test_csv_parsing(tmp_path: Path) -> None:
    path = tmp_path / "permissoes.csv"
    path.write_text(
        "user,sector,canView,canEdit\nana@empresa.com,obras,true,sim\nvera@empresa.com,ti,,\n",
        encoding="utf-8",
    )
    assert grants_from_csv(path) == [
        Grant(user="ana@empresa.com", sector="obras", can_view=True, can_edit=True),
        Grant(user="vera@empresa.com", sector="ti", can_view=True, can_edit=False),
    ]

    bad = tmp_path / "ruim.csv"
    bad.write_text("user,sector,canEdit\nana@empresa.com,obras,talvez\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Linha 2"):
        grants_from_csv(bad)


async def test_cli_requires_explicit_target(db_session, capsys) -> None:
    await _setup(db_session)
    # Sem --user/--sector não faz nada.
    assert await main([]) == 2
    assert await main(["--all-sectors"]) == 2
    assert await _permissions(db_session) == []

    assert await main(["--user", "ana@empresa.com", "--sector", "obras", "--can-edit"]) == 0
    assert await main(["--list", "--user", "ana@empresa.com"]) == 0
    assert "ana@empresa.com (ANALYST) × obras: canView=True canEdit=True" in capsys.readouterr().out

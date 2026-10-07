"""Configuração administrativa e idempotente de UserSectorPermission.

Nunca roda sozinho (nem em migrations): toda concessão é explícita, por
usuário e setor. Usuário sem permissão de setor continua sem ver contratos.
ADMIN não precisa de permissões — o script as ignora.

Uso (a partir de backend/):
    # Consultar
    python scripts/configure_user_sectors.py --list
    python scripts/configure_user_sectors.py --list --user ana@empresa.com

    # Conceder (upsert; não remove outros setores do usuário)
    python scripts/configure_user_sectors.py --user ana@empresa.com --sector projetos-arquitetura
    python scripts/configure_user_sectors.py --user ana@empresa.com --sector projetos-arquitetura --can-edit

    # Revogar
    python scripts/configure_user_sectors.py --user ana@empresa.com --sector projetos-arquitetura --revoke

    # Lote via CSV (colunas: user,sector,canView,canEdit)
    python scripts/configure_user_sectors.py --csv permissoes.csv

    # Só development/test: todos os setores ativos para UM usuário
    python scripts/configure_user_sectors.py --user dev@example.com --all-sectors

Use --dry-run para ver o plano sem gravar. `--user` aceita e-mail ou id;
`--sector` aceita slug ou id e pode ser repetido.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.contracts import Sector, UserSectorPermission  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.shared.audit import record_audit  # noqa: E402

AUDIT_ACTION = "user.sector_permissions.bootstrap"
ALL_SECTORS_ENVS = frozenset({"development", "test"})


class ConfigError(Exception):
    """Entrada inválida — o script para sem gravar nada."""


@dataclass(frozen=True, slots=True)
class Grant:
    user: str
    sector: str
    can_view: bool = True
    can_edit: bool = False
    revoke: bool = False


async def _find_user(session: AsyncSession, ref: str) -> User:
    user = await session.get(User, ref)
    if user is None:
        matches = (
            (await session.execute(select(User).where(func.lower(User.email) == ref.strip().lower())))
            .scalars()
            .all()
        )
        if len(matches) > 1:
            raise ConfigError(f"Mais de um usuário com o e-mail {ref!r}; use o id")
        user = matches[0] if matches else None
    if user is None:
        raise ConfigError(f"Usuário não encontrado: {ref!r}")
    return user


async def _find_sector(session: AsyncSession, ref: str) -> Sector:
    sector = await session.get(Sector, ref)
    if sector is None:
        sector = (
            await session.execute(select(Sector).where(Sector.slug == ref.strip()))
        ).scalar_one_or_none()
    if sector is None:
        raise ConfigError(f"Setor não encontrado: {ref!r}")
    return sector


def _state(permission: UserSectorPermission | None) -> dict[str, bool] | None:
    if permission is None:
        return None
    return {"canView": permission.canView, "canEdit": permission.canEdit}


async def apply_grants(session: AsyncSession, grants: list[Grant], *, dry_run: bool = False) -> list[str]:
    """Aplica as concessões/revogações. Tudo ou nada: qualquer erro desfaz o lote."""
    report: list[str] = []
    try:
        for grant in grants:
            user = await _find_user(session, grant.user)
            sector = await _find_sector(session, grant.sector)
            label = f"{user.email} × {sector.slug}"

            if not user.active:
                raise ConfigError(f"Usuário inativo: {user.email}")
            if user.role == Role.ADMIN:
                report.append(f"ignorado  {label}: ADMIN já acessa todos os setores")
                continue

            current = (
                await session.execute(
                    select(UserSectorPermission).where(
                        UserSectorPermission.userId == user.id, UserSectorPermission.sectorId == sector.id
                    )
                )
            ).scalar_one_or_none()
            before = _state(current)

            if grant.revoke or not (grant.can_view or grant.can_edit):
                if current is None:
                    report.append(f"sem mudança {label}: já sem acesso")
                    continue
                await session.delete(current)
                after = None
                report.append(f"revogado  {label}")
            else:
                # Quem edita também precisa consultar o setor.
                wanted = {"canView": grant.can_view or grant.can_edit, "canEdit": grant.can_edit}
                if before == wanted:
                    report.append(f"sem mudança {label}: {wanted}")
                    continue
                if current is None:
                    session.add(UserSectorPermission(userId=user.id, sectorId=sector.id, **wanted))
                else:
                    current.canView = wanted["canView"]
                    current.canEdit = wanted["canEdit"]
                after = wanted
                note = (
                    " (VIEWER nunca edita, mesmo com canEdit)"
                    if grant.can_edit and user.role == Role.VIEWER
                    else ""
                )
                report.append(f"{'criado' if before is None else 'alterado'}   {label}: {wanted}{note}")

            await session.flush()
            await record_audit(
                session,
                action=AUDIT_ACTION,
                entity="User",
                entity_id=user.id,
                previous_data={"sectorId": sector.id, "permission": before},
                new_data={"sectorId": sector.id, "permission": after},
                metadata={"source": "scripts/configure_user_sectors.py"},
            )
    except Exception:
        await session.rollback()
        raise

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return report


async def all_sector_grants(
    session: AsyncSession, user_ref: str, *, can_edit: bool, app_env: str
) -> list[Grant]:
    """Todos os setores ativos para UM usuário — bloqueado fora de development/test."""
    if app_env not in ALL_SECTORS_ENVS:
        raise ConfigError(f"--all-sectors é permitido só em development/test (APP_ENV={app_env!r})")
    sectors = (await session.execute(select(Sector.id).where(Sector.active.is_(True)))).scalars().all()
    return [Grant(user=user_ref, sector=sector_id, can_edit=can_edit) for sector_id in sectors]


def _parse_bool(value: str, field: str, line: int) -> bool:
    clean = value.strip().lower()
    if clean in {"true", "1", "sim", "s", "yes", "y"}:
        return True
    if clean in {"false", "0", "nao", "não", "n", "no", ""}:
        return False
    raise ConfigError(f"Linha {line}: valor inválido em {field}: {value!r}")


def grants_from_csv(path: Path) -> list[Grant]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"user", "sector"} - set(reader.fieldnames or [])
        if missing:
            raise ConfigError(f"CSV sem as colunas: {', '.join(sorted(missing))}")
        return [
            Grant(
                user=row["user"].strip(),
                sector=row["sector"].strip(),
                can_view=_parse_bool(row.get("canView") or "true", "canView", line),
                can_edit=_parse_bool(row.get("canEdit") or "false", "canEdit", line),
            )
            for line, row in enumerate(reader, start=2)
        ]


async def list_permissions(session: AsyncSession, user_ref: str | None) -> list[str]:
    stmt = (
        select(User.email, User.role, Sector.slug, UserSectorPermission.canView, UserSectorPermission.canEdit)
        .join(User, User.id == UserSectorPermission.userId)
        .join(Sector, Sector.id == UserSectorPermission.sectorId)
        .order_by(User.email, Sector.slug)
    )
    if user_ref:
        user = await _find_user(session, user_ref)
        stmt = stmt.where(UserSectorPermission.userId == user.id)
    rows = (await session.execute(stmt)).all()
    return [
        f"{email} ({role.value}) × {slug}: canView={can_view} canEdit={can_edit}"
        for email, role, slug, can_view, can_edit in rows
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configura UserSectorPermission de forma explícita.")
    parser.add_argument("--list", action="store_true", help="lista as permissões atuais")
    parser.add_argument("--user", help="e-mail ou id do usuário")
    parser.add_argument("--sector", action="append", default=[], help="slug ou id do setor (repetível)")
    parser.add_argument("--can-edit", action="store_true", help="libera edição (ANALYST)")
    parser.add_argument("--revoke", action="store_true", help="remove o acesso aos setores informados")
    parser.add_argument("--csv", type=Path, help="arquivo com colunas user,sector,canView,canEdit")
    parser.add_argument(
        "--all-sectors", action="store_true", help="todos os setores ativos para --user (só development/test)"
    )
    parser.add_argument("--dry-run", action="store_true", help="mostra o plano sem gravar")
    return parser


async def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = get_settings()

    async with SessionLocal() as session:
        try:
            if args.list:
                for line in await list_permissions(session, args.user):
                    print(line)
                return 0

            if args.csv:
                if args.user or args.sector or args.all_sectors:
                    raise ConfigError("--csv não pode ser combinado com --user/--sector/--all-sectors")
                grants = grants_from_csv(args.csv)
            elif args.all_sectors:
                if not args.user or args.sector or args.revoke:
                    raise ConfigError("--all-sectors exige --user e não aceita --sector/--revoke")
                grants = await all_sector_grants(
                    session, args.user, can_edit=args.can_edit, app_env=settings.app_env
                )
            else:
                if not args.user or not args.sector:
                    raise ConfigError("Informe --user e ao menos um --sector (ou --csv / --list)")
                grants = [
                    Grant(user=args.user, sector=sector, can_edit=args.can_edit, revoke=args.revoke)
                    for sector in args.sector
                ]

            report = await apply_grants(session, grants, dry_run=args.dry_run)
        except ConfigError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 2

    for line in report:
        print(line)
    print("(dry-run: nada foi gravado)" if args.dry_run else f"{len(report)} item(ns) processado(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Prepara as duas contas do login de homologação (AUTH_PROVIDER=homologation).

Cria/atualiza os usuários VIEWER e ADMIN a partir das variáveis de ambiente
(sem senha — ela fica só no hash do ambiente) e libera ao VIEWER a CONSULTA
(canView=true, nunca canEdit) dos setores informados. O ADMIN não precisa de
permissões por setor. Idempotente; nunca roda sozinho nem em migrations.

Uso (a partir de backend/):
    python scripts/bootstrap_homologation_users.py --viewer-sectors projetos-arquitetura
    python scripts/bootstrap_homologation_users.py --viewer-sectors all
    python scripts/bootstrap_homologation_users.py --dry-run --viewer-sectors all
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.homologation_auth import accounts, upsert_user  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.models.contracts import Sector, UserSectorPermission  # noqa: E402
from app.shared.audit import record_audit  # noqa: E402


async def bootstrap(viewer_sectors: list[str], *, dry_run: bool) -> list[str]:
    settings = get_settings()
    if settings.auth_provider != "homologation":
        raise SystemExit("ERRO: AUTH_PROVIDER não é 'homologation'.")
    report: list[str] = []
    async with SessionLocal() as session:
        users = {account.role: await upsert_user(session, account) for account in accounts(settings).values()}
        for role, user in users.items():
            report.append(f"usuário {role.value}: {user.externalUserId} (id={user.id})")

        viewer = users.get(Role.VIEWER)
        if viewer is not None and viewer_sectors:
            stmt = select(Sector).where(Sector.active.is_(True))
            if viewer_sectors != ["all"]:
                stmt = stmt.where(Sector.slug.in_(viewer_sectors))
            sectors = (await session.execute(stmt)).scalars().all()
            missing = set(viewer_sectors) - {"all"} - {sector.slug for sector in sectors}
            if missing:
                raise SystemExit(f"ERRO: setor(es) não encontrado(s): {', '.join(sorted(missing))}")
            for sector in sectors:
                current = (
                    await session.execute(
                        select(UserSectorPermission).where(
                            UserSectorPermission.userId == viewer.id,
                            UserSectorPermission.sectorId == sector.id,
                        )
                    )
                ).scalar_one_or_none()
                if current is None:
                    session.add(
                        UserSectorPermission(
                            userId=viewer.id, sectorId=sector.id, canView=True, canEdit=False
                        )
                    )
                    report.append(f"VIEWER: consulta liberada em {sector.slug}")
                else:
                    changed = not current.canView or current.canEdit
                    current.canView, current.canEdit = True, False
                    report.append(
                        f"VIEWER: {sector.slug} {'ajustado para só consulta' if changed else 'sem mudança'}"
                    )
                await record_audit(
                    session,
                    action="user.sector_permissions.bootstrap",
                    entity="User",
                    entity_id=viewer.id,
                    new_data={"sectorId": sector.id, "permission": {"canView": True, "canEdit": False}},
                    metadata={"source": "scripts/bootstrap_homologation_users.py"},
                )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    await engine.dispose()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepara as contas do login de homologação.")
    parser.add_argument(
        "--viewer-sectors",
        nargs="*",
        default=[],
        help="slugs dos setores que o VIEWER pode consultar, ou 'all' para todos os ativos",
    )
    parser.add_argument("--dry-run", action="store_true", help="mostra o que faria sem gravar")
    args = parser.parse_args(argv)
    for line in asyncio.run(bootstrap(args.viewer_sectors, dry_run=args.dry_run)):
        print(line)
    print("(dry-run: nada foi gravado)" if args.dry_run else "Concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

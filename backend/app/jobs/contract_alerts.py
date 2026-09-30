"""Job diário dos alertas de vencimento de contratos.

Executado por um agendador externo (ex.: Render Cron Job), uma vez por dia —
nunca dentro do processo FastAPI:

    python -m app.jobs.contract_alerts             # execução real
    python -m app.jobs.contract_alerts --dry-run   # só mostra o que seria enviado
    python -m app.jobs.contract_alerts --dry-run --date 2026-10-20

Código de saída: 0 quando o job conclui (mesmo que alguns envios falhem — eles
ficam FAILED para retry); 1 quando o próprio job não consegue executar; 2 para
argumentos inválidos.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.modules.contract_alerts.adapter import get_notification_adapter
from app.modules.contract_alerts.schemas import AlertRunOut
from app.modules.contract_alerts.service import ContractAlertService, preview_alerts

logger = get_logger("app.jobs.contract_alerts")

# Simular outra data num envio real só é permitido fora de produção.
_DATE_OVERRIDE_ENVS = frozenset({"development", "test"})


async def run_job(*, dry_run: bool = False, today: date | None = None) -> AlertRunOut:
    try:
        if dry_run:
            return await preview_alerts(today)
        async with SessionLocal() as session:
            return await ContractAlertService(session, get_notification_adapter()).run(today=today)
    finally:
        await engine.dispose()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alertas de vencimento de contratos")
    parser.add_argument("--dry-run", action="store_true", help="não envia nem grava nada")
    parser.add_argument("--date", type=date.fromisoformat, help="dia de referência AAAA-MM-DD")
    return parser.parse_args(argv)


def _print_summary(result: AlertRunOut) -> None:
    mode = "DRY-RUN (nada foi enviado nem gravado)" if result.dry_run else f"provider={result.provider}"
    print(f"Alertas de contratos — {result.today.isoformat()} — {mode}")
    print(f"  contratos analisados : {result.contracts_analyzed}")
    print(f"  alertas elegíveis    : {result.eligible}")
    print(f"  {'seriam enviados' if result.dry_run else 'enviados'}      : {result.sent}")
    print(f"  duplicados ignorados : {result.duplicates}")
    print(f"  retries              : {result.retried}")
    print(f"  falhas               : {result.failed}")
    print(f"  skips                : {result.skipped}")
    for item in result.items:
        print(
            f"    [{item.action}{' retry' if item.retry else ''}] {item.type.value} "
            f"contrato {item.contract_number} ({item.supplier}) -> {item.recipient or '(sem destinatário)'} "
            f"| vence {item.contract_end_date.isoformat()} ({item.days_to_end:+d} d)"
            f"{' | ' + item.error if item.error else ''}"
        )


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv)
    settings = get_settings()
    if args.date and not args.dry_run and settings.app_env not in _DATE_OVERRIDE_ENVS:
        print("ERRO: --date em execução real só é permitido em development/test", file=sys.stderr)
        return 2

    try:
        result = asyncio.run(run_job(dry_run=args.dry_run, today=args.date))
    except Exception:
        logger.exception("contract_alerts.job_failed")
        return 1

    logger.info(
        "contract_alerts.job_finished",
        today=result.today.isoformat(),
        dry_run=result.dry_run,
        provider=result.provider,
        contracts_analyzed=result.contracts_analyzed,
        eligible=result.eligible,
        sent=result.sent,
        duplicates=result.duplicates,
        retried=result.retried,
        failed=result.failed,
        skipped=result.skipped,
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

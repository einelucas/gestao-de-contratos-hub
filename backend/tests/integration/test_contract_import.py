"""Importação de contratos contra PostgreSQL dedicado a testes."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import date, timedelta
from decimal import Decimal

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.contracts import Contract, OverdueContractTracking, OverdueDailySnapshot, Sector, Supplier
from app.modules.contracts import import_service
from app.modules.contracts.rules import contracts_today

BASE = "/api/v1/contratos/importacao"
HEADERS = import_service.HEADERS


def csv_file(*rows, headers=HEADERS):
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def row(number="OF-1", supplier="Fornecedor Novo", **values):
    fields = {"Contrato": number, "Fornecedor": supplier, **values}
    return [fields.get(header, "") for header in HEADERS]


def xlsx_file(*rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    for cells in rows:
        sheet.append(cells)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def seed(session, *, other=False):
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="  FORNECEDOR   ANTIGO  ")
    session.add_all([sector, supplier])
    second = Sector(slug="ti", name="TI", acronym="TI") if other else None
    if second:
        session.add(second)
    await session.flush()
    old = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="PROVISORIO",
        endDate=contracts_today() - timedelta(days=5),
        notify=True,
    )
    session.add(old)
    if second:
        session.add(Contract(sectorId=second.id, supplierId=supplier.id, contractNumber="TI-1"))
    await session.commit()
    return sector, second, supplier, old


async def preview(client, auth_header, sector_id, content, filename="oficiais.csv"):
    return await client.post(
        f"{BASE}/preview",
        data={"sectorId": sector_id},
        files={"file": (filename, content)},
        headers=auth_header("ADMIN"),
    )


async def confirm(client, auth_header, sector_id, content, pre, filename="oficiais.csv"):
    return await client.post(
        f"{BASE}/confirmar",
        data={
            "sectorId": sector_id,
            "expectedSha256": pre["fileSha256"],
            "expectedFingerprint": pre["sectorFingerprint"],
            "confirmReplace": "true",
        },
        files={"file": (filename, content)},
        headers=auth_header("ADMIN"),
    )


async def test_csv_preview_replace_and_supplier_reuse(client, auth_header, db_session) -> None:
    sector, second, supplier, old = await seed(db_session, other=True)
    content = csv_file(
        row(
            "OF-1",
            "fornecedor antigo",
            **{"Valor Serviço": "R$ 1.234,56", "Valor Material Próprio": "5,44", "Unidade": "Lem"},
        ),
        row("OF-2", "Fornecedor Novo", **{"Situação": "Finalizado", "Valor Total": "1234,56"}),
    )
    response = await preview(client, auth_header, sector.id, content)
    assert response.status_code == 200, response.text
    pre = response.json()
    assert pre["canConfirm"] is True
    assert (pre["currentContracts"], pre["rowsFound"], pre["validRows"], pre["newSuppliers"]) == (1, 2, 2, 1)
    assert pre["units"] == ["Lem"]
    assert (await db_session.execute(select(func.count()).select_from(Contract))).scalar_one() == 2
    assert (await db_session.execute(select(func.count()).select_from(Supplier))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(AuditLog))).scalar_one() == 0
    result = await confirm(client, auth_header, sector.id, content, pre)
    assert result.status_code == 200, result.text
    assert result.json() == {"previousCount": 1, "importedCount": 2, "createdSuppliers": 1}
    contracts = (await db_session.execute(select(Contract).order_by(Contract.contractNumber))).scalars().all()
    assert [item.contractNumber for item in contracts] == ["OF-1", "OF-2", "TI-1"]
    assert contracts[0].supplierId == supplier.id and contracts[0].totalValue == Decimal("1240.00")
    assert contracts[1].finalized is True
    assert all(item.notify is False and item.source == "import_csv" for item in contracts[:2])
    assert contracts[2].sectorId == second.id and old.id not in {item.id for item in contracts}
    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "contract.import.replace"))
    ).scalar_one()
    assert (audit.metadata_["previousCount"], audit.metadata_["importedCount"], audit.metadata_["mode"]) == (
        1,
        2,
        "replace",
    )
    assert "content" not in audit.metadata_


async def test_xlsx_excel_dates_and_history_reset(client, auth_header, db_session) -> None:
    sector, _, _, _ = await seed(db_session)
    history = await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN"))
    assert history.status_code == 200
    expired = contracts_today() - timedelta(days=1)
    content = xlsx_file(
        [
            "X-1",
            "Fornecedor Excel",
            "Serviço",
            1234.56,
            0,
            0,
            None,
            date(2024, 1, 1),
            expired,
            "Lem",
            "Vencido",
            "Alta",
            "Sim",
        ],
        ["X-2", "Fornecedor Excel", "", 0, 0, 0, 0, None, None, "", "Finalizado", "", "Não"],
    )
    pre = (await preview(client, auth_header, sector.id, content, "oficiais.xlsx")).json()
    assert pre["canConfirm"] is True and pre["overdueContracts"] == 1 and pre["finalizedContracts"] == 1
    result = await confirm(client, auth_header, sector.id, content, pre, "oficiais.xlsx")
    assert result.status_code == 200, result.text
    contracts = (await db_session.execute(select(Contract).order_by(Contract.contractNumber))).scalars().all()
    assert [item.source for item in contracts] == ["import_xlsx", "import_xlsx"]
    assert contracts[0].startDate == date(2024, 1, 1) and contracts[0].totalValue == Decimal("1234.56")
    assert contracts[0].autoRenewal is True and contracts[1].finalized is True
    snapshots = (await db_session.execute(select(OverdueDailySnapshot))).scalars().all()
    assert len(snapshots) == 1 and snapshots[0].remaining == 1 and snapshots[0].resolvedCumulative == 0
    tracking = (await db_session.execute(select(OverdueContractTracking))).scalars().all()
    assert len(tracking) == 1 and tracking[0].contractId == contracts[0].id


@pytest.mark.parametrize(
    ("content", "column"),
    [
        (csv_file(), "Arquivo"),
        (csv_file(row("", "Fornecedor")), "Contrato"),
        (csv_file(row("1", "")), "Fornecedor"),
        (csv_file(row("1", "F"), row("1", "F")), "Contrato"),
        (csv_file(row("1", "F", **{"Início Vigência": "31/02/2026"})), "inicio vigencia"),
        (csv_file(row("1", "F", **{"Valor Serviço": "inválido"})), "valor servico"),
        (csv_file(row("1", "F", **{"Valor Total": "=1+2"})), "valor total"),
        (csv_file([*row("1", "F"), "extra"]), "Arquivo"),
        (csv_file(row("1", "F"), headers=("Contrato",)), "fornecedor"),
    ],
)
async def test_invalid_preview_blocks_confirmation(client, auth_header, db_session, content, column) -> None:
    sector, _, _, old = await seed(db_session)
    response = await preview(client, auth_header, sector.id, content)
    assert response.status_code == 200, response.text
    pre = response.json()
    assert pre["canConfirm"] is False and any(item["column"] == column for item in pre["issues"])
    assert (await confirm(client, auth_header, sector.id, content, pre)).status_code == 422
    assert (await db_session.execute(select(Contract.id))).scalar_one() == old.id


async def test_partial_history_is_blocked(client, auth_header, db_session) -> None:
    sector, _, _, old = await seed(db_session, other=True)
    await client.get("/api/v1/contratos/vencidos-historico", headers=auth_header("ADMIN"))
    content = csv_file(row())
    pre = (await preview(client, auth_header, sector.id, content)).json()
    assert pre["canConfirm"] is False and any(item["column"] == "Histórico" for item in pre["issues"])
    assert (await confirm(client, auth_header, sector.id, content, pre)).status_code == 409
    assert (await db_session.execute(select(Contract.id).where(Contract.id == old.id))).scalar_one() == old.id


async def test_only_admin_has_import_permission(client, auth_header, db_session) -> None:
    sector, _, _, _ = await seed(db_session)
    content = csv_file(row())
    admin_preview = (await preview(client, auth_header, sector.id, content)).json()
    for role in ("ANALYST", "VIEWER"):
        response = await client.post(
            f"{BASE}/preview",
            data={"sectorId": sector.id},
            files={"file": ("file.csv", content)},
            headers=auth_header(role),
        )
        assert response.status_code == 403
        assert (await client.get(f"{BASE}/modelo", headers=auth_header(role))).status_code == 403
        denied = await client.post(
            f"{BASE}/confirmar",
            data={
                "sectorId": sector.id,
                "expectedSha256": admin_preview["fileSha256"],
                "expectedFingerprint": admin_preview["sectorFingerprint"],
                "confirmReplace": "true",
            },
            files={"file": ("file.csv", content)},
            headers=auth_header(role),
        )
        assert denied.status_code == 403
    template = await client.get(f"{BASE}/modelo", headers=auth_header("ADMIN"))
    assert template.status_code == 200 and template.content.decode("utf-8-sig").startswith(
        "Contrato;Fornecedor;"
    )


async def test_rollback_after_insert_error(client, auth_header, db_session, monkeypatch) -> None:
    sector, _, _, old = await seed(db_session)
    content = csv_file(row())
    pre = (await preview(client, auth_header, sector.id, content)).json()

    async def fail(*args, **kwargs):
        raise RuntimeError("falha simulada após inserts")

    monkeypatch.setattr(import_service, "record_audit", fail)
    with pytest.raises(RuntimeError, match="falha simulada"):
        await confirm(client, auth_header, sector.id, content, pre)
    await db_session.rollback()
    contracts = (await db_session.execute(select(Contract))).scalars().all()
    assert len(contracts) == 1 and contracts[0].id == old.id
    assert (await db_session.execute(select(func.count()).select_from(Supplier))).scalar_one() == 1


async def test_concurrent_confirmation_only_one_wins(client, auth_header, db_session) -> None:
    sector, _, _, _ = await seed(db_session)
    content = csv_file(row())
    pre = (await preview(client, auth_header, sector.id, content)).json()
    first, second = await asyncio.gather(
        confirm(client, auth_header, sector.id, content, pre),
        confirm(client, auth_header, sector.id, content, pre),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert (await db_session.execute(select(func.count()).select_from(Contract))).scalar_one() == 1
    assert (
        await db_session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "contract.import.replace")
        )
    ).scalar_one() == 1


async def test_money_formats_and_text_dates(client, auth_header, db_session) -> None:
    sector, _, _, _ = await seed(db_session)
    content = csv_file(
        row("BR-1", "F1", **{"Valor Total": "R$ 1.234,56", "Início Vigência": "01/10/2025"}),
        row("BR-2", "F2", **{"Valor Total": "1.234,56"}),
        row("BR-3", "F3", **{"Valor Total": "1234,56"}),
    )
    pre = (await preview(client, auth_header, sector.id, content)).json()
    assert pre["canConfirm"] is True
    assert (await confirm(client, auth_header, sector.id, content, pre)).status_code == 200
    imported = (
        (await db_session.execute(select(Contract).where(Contract.sectorId == sector.id))).scalars().all()
    )
    assert len(imported) == 3 and {item.totalValue for item in imported} == {Decimal("1234.56")}
    assert next(item for item in imported if item.contractNumber == "BR-1").startDate == date(2025, 10, 1)


async def test_supplier_is_not_duplicated_within_file(client, auth_header, db_session) -> None:
    sector, _, _, _ = await seed(db_session)
    content = csv_file(row("A", "Fornecedor Único"), row("B", "  fornecedor   único "))
    pre = (await preview(client, auth_header, sector.id, content)).json()
    assert pre["newSuppliers"] == 1
    result = await confirm(client, auth_header, sector.id, content, pre)
    assert result.status_code == 200 and result.json()["createdSuppliers"] == 1
    imported = (
        (await db_session.execute(select(Contract).where(Contract.sectorId == sector.id))).scalars().all()
    )
    assert len({item.supplierId for item in imported}) == 1


async def test_file_or_sector_changed_after_preview_is_rejected(client, auth_header, db_session) -> None:
    sector, _, _, old = await seed(db_session)
    content = csv_file(row("OF-1"))
    pre = (await preview(client, auth_header, sector.id, content)).json()
    changed = await confirm(client, auth_header, sector.id, csv_file(row("OF-2")), pre)
    assert changed.status_code == 409
    db_session.add(Contract(sectorId=sector.id, supplierId=old.supplierId, contractNumber="NOVO"))
    await db_session.commit()
    stale = await confirm(client, auth_header, sector.id, content, pre)
    assert stale.status_code == 409
    assert (await db_session.execute(select(func.count()).select_from(Contract))).scalar_one() == 2


async def test_reject_unsafe_file_and_missing_confirmation(client, auth_header, db_session) -> None:
    sector, _, _, old = await seed(db_session)
    content = csv_file(row())
    rejected = await preview(client, auth_header, sector.id, content, "arquivo.txt")
    assert rejected.status_code == 422
    oversized = await preview(client, auth_header, sector.id, b"x" * (5 * 1024 * 1024 + 1))
    assert oversized.status_code == 422
    pre = (await preview(client, auth_header, sector.id, content)).json()
    missing = await client.post(
        f"{BASE}/confirmar",
        data={
            "sectorId": sector.id,
            "expectedSha256": pre["fileSha256"],
            "expectedFingerprint": pre["sectorFingerprint"],
            "confirmReplace": "false",
        },
        files={"file": ("oficiais.csv", content)},
        headers=auth_header("ADMIN"),
    )
    assert missing.status_code == 422
    assert (await db_session.execute(select(Contract.id))).scalar_one() == old.id

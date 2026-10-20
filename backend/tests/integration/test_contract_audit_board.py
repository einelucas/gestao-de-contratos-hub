"""Kanban de auditoria e sincronização com o status dos contratos."""

from __future__ import annotations

from datetime import timedelta

from app.models.contracts import Contract, Sector, Supplier, UserSectorPermission
from app.modules.contracts.rules import contracts_today

BOARD_URL = "/api/v1/contratos/auditoria"


async def _seed(db_session) -> dict[str, str]:
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor Kanban")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    overdue = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="V-100",
        endDate=contracts_today() - timedelta(days=10),
        unit="Balsas",
    )
    regular = Contract(
        sectorId=sector.id,
        supplierId=supplier.id,
        contractNumber="R-200",
        endDate=contracts_today() + timedelta(days=100),
        unit="LEM",
    )
    db_session.add_all([overdue, regular])
    await db_session.commit()
    return {"sector": sector.id, "overdue": overdue.id, "regular": regular.id}


async def test_overdue_contract_enters_awaiting_analysis_automatically(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)

    response = await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    assert response.status_code == 200
    assert response.json()["units"] == ["Balsas", "LEM"]
    assert [(item["id"], item["auditStage"]) for item in response.json()["items"]] == [
        (ids["overdue"], "AGUARDANDO_ANALISE"),
        (ids["regular"], None),
    ]
    assert response.json()["currentUserId"]
    assert response.json()["users"]


async def test_contracts_inside_five_day_window_enter_awaiting_analysis(
    client, auth_header, db_session
) -> None:
    sector = Sector(slug="obras", name="Obras", acronym="OBR")
    supplier = Supplier(name="Fornecedor Kanban")
    db_session.add_all([sector, supplier])
    await db_session.flush()
    today = contracts_today()

    def contract(number: str, days_to_end: int, **extra) -> Contract:
        return Contract(
            sectorId=sector.id,
            supplierId=supplier.id,
            contractNumber=number,
            endDate=today + timedelta(days=days_to_end),
            **extra,
        )

    due_today = contract("D-0", 0)
    due_in_five = contract("D-5", 5)
    due_in_six = contract("D-6", 6)
    already_started = contract("D-3", 3, auditStage="EM_TRATATIVA")
    finalized_near = contract("D-4", 4, finalized=True)
    dilated = contract(
        "D-2",
        2,
        dilation=True,
        dilationEndDate=today + timedelta(days=60),
    )
    db_session.add_all([due_today, due_in_five, due_in_six, already_started, finalized_near, dilated])
    await db_session.commit()

    response = await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    assert response.status_code == 200
    stages = {item["id"]: item["auditStage"] for item in response.json()["items"]}
    assert stages[due_today.id] == "AGUARDANDO_ANALISE"
    assert stages[due_in_five.id] == "AGUARDANDO_ANALISE"
    assert stages[due_in_six.id] is None
    assert stages[already_started.id] == "EM_TRATATIVA"
    assert stages[finalized_near.id] is None
    assert stages[dilated.id] is None


async def test_new_contract_inside_five_day_window_starts_in_awaiting_analysis(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    response = await client.post(
        "/api/v1/contratos",
        json={
            "sectorId": ids["sector"],
            "supplier": "Fornecedor Kanban",
            "contractNumber": "NOVO-5",
            "serviceDescription": "Serviço",
            "serviceValue": 100,
            "endDate": (contracts_today() + timedelta(days=3)).isoformat(),
        },
        headers=auth_header("ADMIN"),
    )

    assert response.status_code == 201, response.text
    assert response.json()["auditStage"] == "AGUARDANDO_ANALISE"
    assert response.json()["auditStageEnteredAt"]


async def test_moving_to_finalized_updates_contract_and_moving_back_reopens_it(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    move_url = f"/api/v1/contratos/{ids['overdue']}/auditoria"

    in_progress = await client.patch(
        move_url, json={"stage": "EM_TRATATIVA"}, headers=auth_header("ADMIN")
    )
    finalized = await client.patch(
        move_url, json={"stage": "FINALIZADO"}, headers=auth_header("ADMIN")
    )
    reopened = await client.patch(
        move_url, json={"stage": "EM_FINALIZACAO"}, headers=auth_header("ADMIN")
    )

    assert in_progress.status_code == 200
    assert in_progress.json()["auditStage"] == "EM_TRATATIVA"
    assert finalized.status_code == 200
    assert finalized.json()["finalized"] is True
    assert finalized.json()["alert"] == "Finalizado"
    assert reopened.status_code == 200
    assert reopened.json()["finalized"] is False
    assert reopened.json()["alert"] == "Vencido"
    assert reopened.json()["auditStage"] == "EM_FINALIZACAO"


async def test_extending_deadline_reopens_contract_and_returns_it_to_backlog(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    move_url = f"/api/v1/contratos/{ids['overdue']}/auditoria"
    await client.patch(move_url, json={"stage": "FINALIZADO"}, headers=auth_header("ADMIN"))

    extended = await client.patch(
        f"/api/v1/contratos/{ids['overdue']}",
        json={"endDate": (contracts_today() + timedelta(days=120)).isoformat()},
        headers=auth_header("ADMIN"),
    )
    board = await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    assert extended.status_code == 200
    assert extended.json()["finalized"] is False
    assert extended.json()["alert"] == "Regular"
    assert extended.json()["auditStage"] is None
    renewed = next(item for item in board.json()["items"] if item["id"] == ids["overdue"])
    assert renewed["auditStage"] is None


async def test_completing_regularization_returns_awaiting_contract_to_not_started(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    contract_url = f"/api/v1/contratos/{ids['regular']}"
    move_url = f"{contract_url}/auditoria"

    # Contrato regular em auditoria manual, com acompanhamento ainda pendente.
    waiting = await client.patch(
        move_url, json={"stage": "AGUARDANDO_ANALISE"}, headers=auth_header("ADMIN")
    )
    assert waiting.status_code == 200
    assert waiting.json()["auditStage"] == "AGUARDANDO_ANALISE"

    started = await client.patch(
        contract_url,
        json={"regularizationStage": "aguardando_analise"},
        headers=auth_header("ADMIN"),
    )
    assert started.status_code == 200
    assert started.json()["alert"] == "Regularizacao"
    assert started.json()["auditStage"] == "AGUARDANDO_ANALISE"

    regularized = await client.patch(
        contract_url,
        json={"regularizationStage": None},
        headers=auth_header("ADMIN"),
    )
    assert regularized.status_code == 200, regularized.text
    assert regularized.json()["alert"] == "Regular"
    assert regularized.json()["auditStage"] is None
    assert regularized.json()["auditStageEnteredAt"] is None
    assert regularized.json()["regularizationStage"] is None

    board = await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    row = next(item for item in board.json()["items"] if item["id"] == ids["regular"])
    assert row["auditStage"] is None


async def test_regularization_does_not_reset_advanced_manual_audit_stages(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    contract_url = f"/api/v1/contratos/{ids['regular']}"
    move = await client.patch(
        f"{contract_url}/auditoria",
        json={"stage": "EM_TRATATIVA"},
        headers=auth_header("ADMIN"),
    )
    assert move.status_code == 200

    await client.patch(
        contract_url,
        json={"regularizationStage": "em_tratativa"},
        headers=auth_header("ADMIN"),
    )
    regularized = await client.patch(
        contract_url,
        json={"regularizationStage": None},
        headers=auth_header("ADMIN"),
    )
    assert regularized.status_code == 200, regularized.text
    assert regularized.json()["alert"] == "Regular"
    assert regularized.json()["auditStage"] == "EM_TRATATIVA"


async def test_renewing_contract_does_not_reset_advanced_manual_audit_stage(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    contract_url = f"/api/v1/contratos/{ids['overdue']}"
    await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    moved = await client.patch(
        f"{contract_url}/auditoria",
        json={"stage": "EM_TRATATIVA"},
        headers=auth_header("ADMIN"),
    )
    assert moved.status_code == 200

    renewed = await client.patch(
        contract_url,
        json={"endDate": (contracts_today() + timedelta(days=120)).isoformat()},
        headers=auth_header("ADMIN"),
    )
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["alert"] == "Regular"
    assert renewed.json()["auditStage"] == "EM_TRATATIVA"

    board = await client.get(BOARD_URL, headers=auth_header("ADMIN"))
    row = next(item for item in board.json()["items"] if item["id"] == ids["overdue"])
    assert row["auditStage"] == "EM_TRATATIVA"


async def test_regularization_keeps_awaiting_when_contract_still_due_soon(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    contract_url = f"/api/v1/contratos/{ids['overdue']}"
    await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    started = await client.patch(
        contract_url,
        json={"regularizationStage": "aguardando_analise"},
        headers=auth_header("ADMIN"),
    )
    assert started.status_code == 200

    # Renovou, mas a nova vigência ainda está na janela de cinco dias.
    renewed = await client.patch(
        contract_url,
        json={
            "endDate": (contracts_today() + timedelta(days=3)).isoformat(),
            "regularizationStage": None,
        },
        headers=auth_header("ADMIN"),
    )
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["alert"] == "Atencao"
    assert renewed.json()["auditStage"] == "AGUARDANDO_ANALISE"


async def test_regular_contract_can_start_audit_and_workspace_is_persisted(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    move = await client.patch(
        f"/api/v1/contratos/{ids['regular']}/auditoria",
        json={"stage": "AGUARDANDO_ANALISE"},
        headers=auth_header("ADMIN"),
    )
    assert move.status_code == 200, move.text
    assert move.json()["auditStage"] == "AGUARDANDO_ANALISE"
    assert move.json()["auditStageEnteredAt"]

    update = await client.post(
        f"/api/v1/contratos/{ids['regular']}/auditoria/atualizacoes",
        data={"text": "Validar documento com @Dev Admin", "mentionedUserIds": "[]"},
        files={"files": ("evidencia.txt", b"conteudo", "text/plain")},
        headers=auth_header("ADMIN"),
    )
    assert update.status_code == 201, update.text
    assert update.json()["text"] == "Validar documento com @Dev Admin"
    assert update.json()["attachments"][0]["name"] == "evidencia.txt"

    workspace = await client.get(
        f"/api/v1/contratos/{ids['regular']}/auditoria/workspace",
        headers=auth_header("ADMIN"),
    )
    assert workspace.status_code == 200
    assert len(workspace.json()["updates"]) == 1
    assert [event["type"] for event in workspace.json()["activity"]] == ["FILE", "STAGE"]

    attachment_id = workspace.json()["updates"][0]["attachments"][0]["id"]
    attachment = await client.get(
        f"/api/v1/contratos/auditoria/anexos/{attachment_id}",
        headers=auth_header("ADMIN"),
    )
    assert attachment.status_code == 200
    assert attachment.content == b"conteudo"


async def test_board_and_moves_respect_sector_permissions(client, auth_header, db_session) -> None:
    ids = await _seed(db_session)
    viewer = await client.get("/api/v1/auth/me", headers=auth_header("VIEWER"))
    viewer_id = viewer.json()["id"]
    db_session.add(
        UserSectorPermission(
            userId=viewer_id, sectorId=ids["sector"], canView=True, canEdit=False
        )
    )
    await db_session.commit()

    board = await client.get(BOARD_URL, headers=auth_header("VIEWER"))
    move = await client.patch(
        f"/api/v1/contratos/{ids['overdue']}/auditoria",
        json={"stage": "EM_TRATATIVA"},
        headers=auth_header("VIEWER"),
    )

    assert board.status_code == 200
    assert board.json()["items"][0]["canEdit"] is False
    assert move.status_code == 403


async def test_board_reports_mentions_for_current_user(
    client, auth_header, db_session
) -> None:
    ids = await _seed(db_session)
    viewer = (await client.get("/api/v1/auth/me", headers=auth_header("VIEWER"))).json()
    db_session.add(
        UserSectorPermission(
            userId=viewer["id"], sectorId=ids["sector"], canView=True, canEdit=False
        )
    )
    await db_session.commit()

    created = await client.post(
        f"/api/v1/contratos/{ids['regular']}/auditoria/atualizacoes",
        data={
            "text": f"Validar com @{viewer['name']}",
            "mentionedUserIds": f'["{viewer["id"]}"]',
        },
        headers=auth_header("ADMIN"),
    )

    viewer_board = await client.get(BOARD_URL, headers=auth_header("VIEWER"))
    admin_board = await client.get(BOARD_URL, headers=auth_header("ADMIN"))

    assert created.status_code == 201, created.text
    assert created.json()["mentionedUserIds"] == [viewer["id"]]
    assert viewer_board.status_code == 200
    assert viewer_board.json()["mentionCounts"] == {ids["regular"]: 1}
    assert admin_board.json()["mentionCounts"] == {}

"""Testes de integração HTTP de `/auditoria`."""

from __future__ import annotations


async def test_audit_requires_admin(client, auth_header) -> None:
    forbidden = await client.get("/api/v1/auditoria", headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403


async def test_audit_lists_entries_produced_by_user_changes(client, auth_header) -> None:
    created = await client.post(
        "/api/v1/usuarios",
        json={"name": "Ana Souza", "email": "ana.audit@example.com", "role": "VIEWER"},
        headers=auth_header("ADMIN"),
    )
    assert created.status_code == 201

    response = await client.get("/api/v1/auditoria", headers=auth_header("ADMIN"))
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    actions = {item["action"] for item in body["items"]}
    assert "user.create" in actions


async def test_audit_pagination_page_size_capped(client, auth_header) -> None:
    response = await client.get("/api/v1/auditoria?pageSize=1000", headers=auth_header("ADMIN"))
    assert response.status_code == 200
    assert response.json()["pagination"]["pageSize"] <= 100

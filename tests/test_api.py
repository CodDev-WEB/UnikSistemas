from fastapi.testclient import TestClient


def provision(client: TestClient, slug: str, email: str) -> dict:
    response = client.post(
        "/api/v1/setup/tenants",
        headers={"X-Bootstrap-Token": "test-bootstrap-token-with-more-than-thirty-two"},
        json={
            "tenant_name": f"Escritório {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Responsável Contábil",
            "owner_password": "Senha-Forte-Teste-2026",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, slug: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "tenant_slug": slug,
            "email": email,
            "password": "Senha-Forte-Teste-2026",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_endpoints(client: TestClient):
    assert client.get("/health/live").json()["status"] == "ok"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "ok"


def test_bootstrap_requires_operator_token(client: TestClient):
    response = client.post(
        "/api/v1/setup/tenants",
        json={
            "tenant_name": "Escritório Teste",
            "tenant_slug": "teste",
            "owner_email": "owner@example.com",
            "owner_full_name": "Dono do Escritório",
            "owner_password": "Senha-Forte-Teste-2026",
        },
    )
    assert response.status_code == 403


def test_can_provision_login_and_create_client(client: TestClient):
    provision(client, "escritorio-teste", "owner@example.com")
    token = login(client, "escritorio-teste", "owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["tenant"]["slug"] == "escritorio-teste"
    assert "password_hash" not in me.json()["user"]

    created = client.post(
        "/api/v1/clients",
        headers=headers,
        json={
            "legal_name": "Empresa Exemplo LTDA",
            "trade_name": "Empresa Exemplo",
            "tax_id": "12.345.678/0001-99",
            "email": "financeiro@example.com",
        },
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]

    listed = client.get("/api/v1/clients", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == client_id


def test_tenant_cannot_read_another_tenants_client(client: TestClient):
    provision(client, "escritorio-a", "owner-a@example.com")
    token_a = login(client, "escritorio-a", "owner-a@example.com")
    created = client.post(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"legal_name": "Cliente Privado do A"},
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    provision(client, "escritorio-b", "owner-b@example.com")
    token_b = login(client, "escritorio-b", "owner-b@example.com")
    response = client.get(
        f"/api/v1/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Cliente não encontrado."


def test_invalid_login_is_rejected(client: TestClient):
    provision(client, "escritorio-teste", "owner@example.com")
    response = client.post(
        "/api/v1/auth/token",
        json={
            "tenant_slug": "escritorio-teste",
            "email": "owner@example.com",
            "password": "senha-errada",
        },
    )
    assert response.status_code == 401


def test_endpoints_require_authentication(client: TestClient):
    assert client.get("/api/v1/clients").status_code == 401

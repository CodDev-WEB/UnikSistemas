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



def create_user(
    client: TestClient,
    token: str,
    email: str,
    role: str = "accountant",
    full_name: str = "Pessoa da Equipe",
) -> dict:
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": email,
            "full_name": full_name,
            "password": "Senha-Inicial-Forte-2026",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_can_create_list_update_and_deactivate_users(client: TestClient):
    provision(client, "equipe-a", "owner@example.com")
    owner_token = login(client, "equipe-a", "owner@example.com")
    user = create_user(client, owner_token, "contadora@example.com", "accountant")

    assert user["role"] == "accountant"
    assert user["is_active"] is True
    assert "password_hash" not in user

    listed = client.get("/api/v1/users", headers={"Authorization": f"Bearer {owner_token}"})
    assert listed.status_code == 200
    assert {item["email"] for item in listed.json()} == {
        "owner@example.com",
        "contadora@example.com",
    }

    updated = client.patch(
        f"/api/v1/users/{user['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"role": "assistant"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "assistant"

    deactivated = client.patch(
        f"/api/v1/users/{user['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    denied_login = client.post(
        "/api/v1/auth/token",
        json={
            "tenant_slug": "equipe-a",
            "email": "contadora@example.com",
            "password": "Senha-Inicial-Forte-2026",
        },
    )
    assert denied_login.status_code == 401


def test_non_manager_cannot_manage_users_and_viewer_is_read_only(client: TestClient):
    provision(client, "permissoes", "owner@example.com")
    owner_token = login(client, "permissoes", "owner@example.com")
    accountant = create_user(client, owner_token, "contabil@example.com", "accountant")
    viewer = create_user(client, owner_token, "consulta@example.com", "viewer")

    accountant_token = login(client, "permissoes", "contabil@example.com")
    headers = {"Authorization": f"Bearer {accountant_token}"}
    assert client.get("/api/v1/users", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "outro@example.com",
            "full_name": "Outro Usuário",
            "password": "Senha-Inicial-Forte-2026",
            "role": "accountant",
        },
    ).status_code == 403
    assert client.post(
        "/api/v1/clients",
        headers=headers,
        json={"legal_name": "Cliente Cadastrado Pela Contabilidade"},
    ).status_code == 201

    viewer_token = login(client, "permissoes", "consulta@example.com")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    assert client.get("/api/v1/clients", headers=viewer_headers).status_code == 200
    assert client.post(
        "/api/v1/clients",
        headers=viewer_headers,
        json={"legal_name": "Cadastro Não Permitido"},
    ).status_code == 403
    assert accountant["role"] == "accountant"
    assert viewer["role"] == "viewer"


def test_admin_cannot_create_admin_change_owner_or_disable_self(client: TestClient):
    owner = provision(client, "escritorio-admin", "owner@example.com")
    owner_token = login(client, "escritorio-admin", "owner@example.com")
    admin = create_user(client, owner_token, "admin@example.com", "admin")
    admin_token = login(client, "escritorio-admin", "admin@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    rejected_admin = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "admin2@example.com",
            "full_name": "Outro Admin",
            "password": "Senha-Inicial-Forte-2026",
            "role": "admin",
        },
    )
    assert rejected_admin.status_code == 403

    edit_owner = client.patch(
        f"/api/v1/users/{owner['owner']['id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert edit_owner.status_code == 403

    disable_self = client.patch(
        f"/api/v1/users/{admin['id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disable_self.status_code == 403

    created_staff = create_user(client, admin_token, "assistente@example.com", "assistant")
    assert created_staff["role"] == "assistant"


def test_user_management_is_scoped_to_authenticated_tenant(client: TestClient):
    provision(client, "tenant-a", "owner-a@example.com")
    token_a = login(client, "tenant-a", "owner-a@example.com")
    foreign_user = create_user(client, token_a, "colaborador-a@example.com", "accountant")

    provision(client, "tenant-b", "owner-b@example.com")
    token_b = login(client, "tenant-b", "owner-b@example.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    listing = client.get("/api/v1/users", headers=headers_b)
    assert listing.status_code == 200
    assert {row["email"] for row in listing.json()} == {"owner-b@example.com"}

    update_foreign = client.patch(
        f"/api/v1/users/{foreign_user['id']}",
        headers=headers_b,
        json={"is_active": False},
    )
    assert update_foreign.status_code == 404

from tests.conftest import DEMO_EMAIL, DEMO_PASSWORD


def test_magic_link_always_reports_sent(client):
    resp = client.post("/v1/auth/magic-link", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"sent": True}


def test_login_with_correct_credentials_returns_bearer_token(client):
    resp = client.post("/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_with_wrong_password_is_rejected(client):
    resp = client.post("/v1/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"


def test_login_with_unknown_email_is_rejected(client):
    resp = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


def test_me_requires_bearer_token(client):
    resp = client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthenticated"


def test_me_rejects_garbage_token(client):
    resp = client.get("/v1/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_me_returns_seeded_user(client, owner_headers):
    resp = client.get("/v1/me", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == DEMO_EMAIL
    assert body["display_name"] == "Alex Moreau"


def test_passwords_are_hashed_not_stored_in_plaintext(client):
    store = client.app.state.store
    user = store.find_user_by_email(DEMO_EMAIL)
    stored = store.get_password_hash(user.id)
    assert stored != DEMO_PASSWORD
    assert stored.startswith("$2b$")

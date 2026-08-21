import pytest
from fastapi.testclient import TestClient

from app.main import create_app

DEMO_EMAIL = "interviewer@example.com"
DEMO_PASSWORD = "password123"


@pytest.fixture
def client() -> TestClient:
    # Fresh app + in-memory database per test so seeded data and tokens never leak across tests.
    return TestClient(create_app(database_url="sqlite:///:memory:"))


@pytest.fixture
def owner_token(client: TestClient) -> str:
    resp = client.post("/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def owner_headers(owner_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {owner_token}"}


@pytest.fixture
def live_session_id(client: TestClient, owner_headers: dict[str, str]) -> str:
    resp = client.get("/v1/sessions", headers=owner_headers)
    session = next(s for s in resp.json() if s["title"] == "Design a URL shortener")
    return session["id"]


@pytest.fixture
def draft_session_id(client: TestClient, owner_headers: dict[str, str]) -> str:
    resp = client.get("/v1/sessions", headers=owner_headers)
    session = next(s for s in resp.json() if s["title"] == "Design a rate limiter")
    return session["id"]

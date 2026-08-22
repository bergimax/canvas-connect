"""Fixtures for tests that run against the real docker-compose.yaml stack.

Separate from tests/ (which exercises the app in-process against SQLite):
these spin up the actual Postgres + app containers over the network,
exactly as a user would run them, so they catch things the in-process
suite structurally cannot — e.g. real foreign-key enforcement, the
frontend reverse proxy, and data surviving a container restart.

Not picked up by `make test` (pyproject's testpaths is just ["tests"]);
run explicitly with `make test-integration` since it's slow and requires
Docker.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
BASE_URL = "http://localhost:8000"

DEMO_EMAIL = "interviewer@example.com"
DEMO_PASSWORD = "password123"


def _compose(*args: str) -> None:
    subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), *args], cwd=REPO_ROOT, check=True)


@pytest.fixture(scope="session", autouse=True)
def compose_stack():
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0:
        pytest.skip("docker compose is not available")

    # Clean slate: a stray container from previous manual testing on the
    # same port, or a leftover volume from a previous failed run, would
    # otherwise make these tests flaky.
    _compose("down", "-v")
    _compose("up", "-d", "--wait", "--wait-timeout", "60")
    wait_until_reachable(BASE_URL)
    try:
        yield
    finally:
        _compose("down", "-v")


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


@pytest.fixture
def owner_token(client: httpx.Client) -> str:
    resp = client.post("/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def owner_headers(owner_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {owner_token}"}


def wait_until_reachable(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            httpx.get(url, timeout=2).raise_for_status()
            return
        except (httpx.HTTPError, httpx.TransportError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"{url} did not become reachable") from last_error

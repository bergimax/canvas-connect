"""Integration scenarios against the real docker-compose.yaml stack.

See conftest.py for what these are for and why they're separate from
tests/. Each test below targets something the in-process SQLite suite
can't: real network calls, real Postgres FK enforcement, the frontend
reverse proxy, or container-restart persistence.
"""

import re
from datetime import datetime, timezone

from .conftest import BASE_URL, DEMO_EMAIL, DEMO_PASSWORD, wait_until_reachable, _compose


def test_frontend_is_served_by_backend(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Canvas Connect" in resp.text

    # Client-side route, not a backend endpoint — must come from the
    # proxied frontend server, not a FastAPI 404.
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404


def test_frontend_static_assets_resolve_through_the_proxy(client):
    html = client.get("/").text
    match = re.search(r'href="(/assets/[^"]+\.css)"', html)
    assert match, "expected a hashed CSS asset link in the served HTML"
    resp = client.get(match.group(1))
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_auth_flow_against_real_postgres(client):
    resp = client.get("/v1/sessions")
    assert resp.status_code == 401

    resp = client.post("/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = client.get("/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_create_session_against_real_postgres(client, owner_headers):
    # Regression test: create_session inserts a sessions row and an FK'd
    # canvas_documents row in the same commit with no relationship()
    # ordering them. SQLite never enforces the FK and let this slide;
    # only a real Postgres server rejects it if the order is wrong.
    resp = client.post(
        "/v1/sessions",
        headers=owner_headers,
        json={"title": "Integration test session", "prompt": "Does the FK insert order hold?"},
    )
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    resp = client.get(f"/v1/sessions/{session_id}/canvas", headers=owner_headers)
    assert resp.status_code == 200


def test_duplicate_session_against_real_postgres(client, owner_headers):
    # Same regression as above, for duplicate_session's independent copy
    # of the same insert-ordering bug.
    resp = client.get("/v1/sessions", headers=owner_headers)
    source_id = resp.json()[0]["id"]

    resp = client.post(f"/v1/sessions/{source_id}/duplicate", headers=owner_headers)
    assert resp.status_code == 201
    duplicate_id = resp.json()["id"]

    resp = client.get(f"/v1/sessions/{duplicate_id}/canvas", headers=owner_headers)
    assert resp.status_code == 200


def test_guest_join_and_canvas_flow(client, owner_headers):
    resp = client.post(
        "/v1/sessions",
        headers=owner_headers,
        json={"title": "Guest flow session", "prompt": "..."},
    )
    session_id = resp.json()["id"]
    client.post(f"/v1/sessions/{session_id}/start", headers=owner_headers)

    resp = client.post(f"/v1/sessions/{session_id}/guest-links", json={"role": "candidate"}, headers=owner_headers)
    assert resp.status_code == 201
    guest_token_in_url = resp.json()["url"].rsplit("/", 1)[-1]

    resp = client.get(f"/v1/join/{guest_token_in_url}")
    assert resp.status_code == 200
    assert resp.json()["joinable"] is True

    resp = client.post(f"/v1/join/{guest_token_in_url}", json={"display_name": "Test Candidate"})
    assert resp.status_code == 201
    collaboration_token = resp.json()["collaboration_token"]
    participant_id = resp.json()["participant"]["id"]
    guest_headers = {"Authorization": f"Bearer {collaboration_token}"}

    resp = client.get(f"/v1/sessions/{session_id}/canvas", headers=guest_headers)
    assert resp.status_code == 200
    document = resp.json()["document"]

    now = datetime.now(timezone.utc).isoformat()
    resp = client.put(
        f"/v1/sessions/{session_id}/canvas",
        headers=guest_headers,
        json={
            "id": document["id"],
            "session_id": session_id,
            "schema_version": document["schema_version"],
            "latest_operation_cursor": document["latest_operation_cursor"] + 1,
            "updated_at": now,
            "elements": [
                {
                    "id": "el_1",
                    "x": 0,
                    "y": 0,
                    "z": 0,
                    "created_by": participant_id,
                    "created_at": now,
                    "updated_at": now,
                    "kind": "shape",
                    "shape": "rect",
                    "width": 100,
                    "height": 50,
                    "label": "Test box",
                }
            ],
        },
    )
    assert resp.status_code == 200

    resp = client.get(f"/v1/sessions/{session_id}", headers=owner_headers)
    assert len(resp.json()["participants"]) == 2


def test_data_persists_across_app_restart(client, owner_headers):
    resp = client.post(
        "/v1/sessions",
        headers=owner_headers,
        json={"title": "Should survive a restart", "prompt": "..."},
    )
    assert resp.status_code == 201

    _compose("restart", "app")
    wait_until_reachable(BASE_URL)

    resp = client.get("/v1/sessions", headers=owner_headers)
    assert resp.status_code == 200
    titles = {s["title"] for s in resp.json()}
    assert "Should survive a restart" in titles

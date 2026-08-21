def test_list_sessions_excludes_archived(client, owner_headers):
    resp = client.get("/v1/sessions", headers=owner_headers)
    assert resp.status_code == 200
    titles = {s["title"] for s in resp.json()}
    assert "Design a URL shortener" in titles
    assert all(s["state"] != "archived" for s in resp.json())


def test_list_sessions_requires_auth(client):
    resp = client.get("/v1/sessions")
    assert resp.status_code == 401


def test_create_session_becomes_owner(client, owner_headers):
    resp = client.post(
        "/v1/sessions",
        headers=owner_headers,
        json={"title": "Design a payments ledger", "prompt": "Design it."},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Design a payments ledger"
    assert body["state"] == "draft"
    assert len(body["participants"]) == 1
    assert body["participants"][0]["role"] == "owner"


def test_get_session_not_found(client, owner_headers):
    resp = client.get("/v1/sessions/does-not-exist", headers=owner_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_update_session_patches_only_supplied_fields(client, owner_headers, draft_session_id):
    resp = client.patch(
        f"/v1/sessions/{draft_session_id}",
        headers=owner_headers,
        json={"title": "Design a smarter rate limiter"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Design a smarter rate limiter"
    assert body["prompt"] == "Design a distributed rate limiter for a public API gateway."


def test_start_session_transitions_to_live(client, owner_headers, draft_session_id):
    resp = client.post(f"/v1/sessions/{draft_session_id}/start", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "live"
    assert body["started_at"] is not None


def test_end_session_disables_candidate_editing(client, owner_headers, live_session_id):
    resp = client.post(f"/v1/sessions/{live_session_id}/end", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "ended"
    assert body["candidate_editing_enabled"] is False


def test_end_session_twice_is_conflict(client, owner_headers, live_session_id):
    client.post(f"/v1/sessions/{live_session_id}/end", headers=owner_headers)
    resp = client.post(f"/v1/sessions/{live_session_id}/end", headers=owner_headers)
    assert resp.status_code == 409


def test_archive_session(client, owner_headers, draft_session_id):
    resp = client.post(f"/v1/sessions/{draft_session_id}/archive", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["state"] == "archived"

    listed = client.get("/v1/sessions", headers=owner_headers)
    assert draft_session_id not in {s["id"] for s in listed.json()}


def test_duplicate_session_copies_canvas_and_resets_lifecycle(client, owner_headers, live_session_id):
    resp = client.post(f"/v1/sessions/{live_session_id}/duplicate", headers=owner_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] != live_session_id
    assert body["title"] == "Design a URL shortener (copy)"
    assert body["state"] == "draft"
    assert body["started_at"] is None
    assert len(body["participants"]) == 1

    canvas = client.get(f"/v1/sessions/{body['id']}/canvas", headers=owner_headers)
    assert len(canvas.json()["document"]["elements"]) == 9


def test_only_owner_can_start_session(client, owner_headers, draft_session_id):
    # A candidate joining via guest link cannot start the session.
    link = client.post(f"/v1/sessions/{draft_session_id}/guest-links", headers=owner_headers, json={})
    token = link.json()["url"].rsplit("/", 1)[-1]
    join = client.post(f"/v1/join/{token}", json={"display_name": "Guest"})
    guest_headers = {"Authorization": f"Bearer {join.json()['collaboration_token']}"}

    resp = client.post(f"/v1/sessions/{draft_session_id}/start", headers=guest_headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "forbidden"


def test_non_participant_cannot_read_session(client, owner_headers):
    # A second interviewer account with no relationship to the seeded session.
    other = client.app.state.store.create_user(
        email="other@example.com", display_name="Other Interviewer", password="password123"
    )
    other_token = client.app.state.store.issue_user_token(other.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    sessions = client.get("/v1/sessions", headers=owner_headers).json()
    session_id = sessions[0]["id"]

    resp = client.get(f"/v1/sessions/{session_id}", headers=other_headers)
    assert resp.status_code == 403

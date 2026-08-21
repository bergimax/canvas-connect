def test_preview_invalid_token(client):
    resp = client.get("/v1/join/not-a-real-token")
    assert resp.status_code == 200
    body = resp.json()
    assert body["joinable"] is False
    assert body["reason"] == "This link is not valid."


def test_preview_valid_token(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]

    resp = client.get(f"/v1/join/{token}")
    assert resp.status_code == 200
    assert resp.json() == {"session_title": "Design a URL shortener", "joinable": True, "reason": None}


def test_join_creates_candidate_participant_and_token(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]

    resp = client.post(f"/v1/join/{token}", json={"display_name": "Casey Candidate"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["participant"]["display_name"] == "Casey Candidate"
    assert body["participant"]["role"] == "candidate"
    assert body["collaboration_token"]

    # The token actually authenticates subsequent requests.
    guest_headers = {"Authorization": f"Bearer {body['collaboration_token']}"}
    me_like = client.get(f"/v1/sessions/{live_session_id}", headers=guest_headers)
    assert me_like.status_code == 200


def test_join_revoked_link_is_conflict(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]
    client.delete(f"/v1/sessions/{live_session_id}/guest-links/{link['id']}", headers=owner_headers)

    resp = client.post(f"/v1/join/{token}", json={"display_name": "Too Late"})
    assert resp.status_code == 409


def test_join_archived_session_is_conflict(client, owner_headers, draft_session_id):
    link = client.post(f"/v1/sessions/{draft_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]
    client.post(f"/v1/sessions/{draft_session_id}/archive", headers=owner_headers)

    resp = client.post(f"/v1/join/{token}", json={"display_name": "Too Late"})
    assert resp.status_code == 409


def test_join_at_capacity_is_conflict(client, owner_headers, live_session_id):
    link = client.post(
        f"/v1/sessions/{live_session_id}/guest-links",
        headers=owner_headers,
        json={"max_uses": 1},
    ).json()
    token = link["url"].rsplit("/", 1)[-1]

    first = client.post(f"/v1/join/{token}", json={"display_name": "First"})
    assert first.status_code == 201

    second = client.post(f"/v1/join/{token}", json={"display_name": "Second"})
    assert second.status_code == 409


def test_join_invalid_token_is_not_found(client):
    resp = client.post("/v1/join/bogus", json={"display_name": "Nobody"})
    assert resp.status_code == 404


def test_join_moves_draft_session_to_live(client, owner_headers, draft_session_id):
    link = client.post(f"/v1/sessions/{draft_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]

    resp = client.post(f"/v1/join/{token}", json={"display_name": "First Candidate"})
    assert resp.status_code == 201
    assert resp.json()["session"]["state"] == "live"

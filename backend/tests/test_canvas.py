def _join_as(client, owner_headers, session_id, role="candidate", display_name="Guest"):
    link = client.post(
        f"/v1/sessions/{session_id}/guest-links",
        headers=owner_headers,
        json={"role_granted": role},
    ).json()
    token = link["url"].rsplit("/", 1)[-1]
    joined = client.post(f"/v1/join/{token}", json={"display_name": display_name}).json()
    return {"Authorization": f"Bearer {joined['collaboration_token']}"}


def test_get_canvas_returns_seeded_elements(client, owner_headers, live_session_id):
    resp = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["document"]["elements"]) == 9
    assert body["websocket_url"] == ""
    assert body["collaboration_token"]


def test_get_canvas_requires_membership(client, owner_headers, live_session_id):
    other = client.app.state.store.create_user(email="other@example.com", display_name="Other", password="x")
    other_headers = {"Authorization": f"Bearer {client.app.state.store.issue_user_token(other.id)}"}

    resp = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=other_headers)
    assert resp.status_code == 403


def test_owner_can_save_canvas(client, owner_headers, live_session_id):
    doc = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=owner_headers).json()["document"]
    doc["elements"] = []
    resp = client.put(f"/v1/sessions/{live_session_id}/canvas", headers=owner_headers, json=doc)
    assert resp.status_code == 200
    assert "saved_at" in resp.json()

    refetched = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=owner_headers).json()
    assert refetched["document"]["elements"] == []


def test_candidate_can_save_when_editing_enabled(client, owner_headers, live_session_id):
    guest_headers = _join_as(client, owner_headers, live_session_id)
    doc = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=guest_headers).json()["document"]

    resp = client.put(f"/v1/sessions/{live_session_id}/canvas", headers=guest_headers, json=doc)
    assert resp.status_code == 200


def test_candidate_cannot_save_when_editing_disabled(client, owner_headers, live_session_id):
    guest_headers = _join_as(client, owner_headers, live_session_id)
    client.patch(
        f"/v1/sessions/{live_session_id}",
        headers=owner_headers,
        json={"candidate_editing_enabled": False},
    )
    doc = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=guest_headers).json()["document"]

    resp = client.put(f"/v1/sessions/{live_session_id}/canvas", headers=guest_headers, json=doc)
    assert resp.status_code == 403


def test_observer_cannot_save_canvas(client, owner_headers, live_session_id):
    observer_headers = _join_as(client, owner_headers, live_session_id, role="observer", display_name="Watcher")
    doc = client.get(f"/v1/sessions/{live_session_id}/canvas", headers=observer_headers).json()["document"]

    resp = client.put(f"/v1/sessions/{live_session_id}/canvas", headers=observer_headers, json=doc)
    assert resp.status_code == 403

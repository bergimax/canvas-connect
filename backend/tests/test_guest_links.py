def test_create_guest_link_defaults_to_candidate_role(client, owner_headers, live_session_id):
    resp = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["role_granted"] == "candidate"
    assert body["revoked_at"] is None
    assert "/join/" in body["url"]


def test_creating_a_new_link_revokes_the_previous_one(client, owner_headers, live_session_id):
    first = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={})
    second = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={})
    assert first.status_code == 201
    assert second.status_code == 201

    active = client.get(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers).json()
    ids = {link["id"] for link in active}
    assert first.json()["id"] not in ids
    assert second.json()["id"] in ids


def test_revoke_guest_link(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    resp = client.delete(f"/v1/sessions/{live_session_id}/guest-links/{link['id']}", headers=owner_headers)
    assert resp.status_code == 204

    active = client.get(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers).json()
    assert active == []


def test_guest_cannot_create_guest_links(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]
    join = client.post(f"/v1/join/{token}", json={"display_name": "Guest"})
    guest_headers = {"Authorization": f"Bearer {join.json()['collaboration_token']}"}

    resp = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=guest_headers, json={})
    assert resp.status_code == 403


def test_guest_link_can_grant_observer_role(client, owner_headers, live_session_id):
    link = client.post(
        f"/v1/sessions/{live_session_id}/guest-links",
        headers=owner_headers,
        json={"role_granted": "observer"},
    ).json()
    token = link["url"].rsplit("/", 1)[-1]
    join = client.post(f"/v1/join/{token}", json={"display_name": "Watcher"})
    assert join.status_code == 201
    assert join.json()["participant"]["role"] == "observer"

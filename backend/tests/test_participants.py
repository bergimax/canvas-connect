def test_owner_can_remove_participant(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]
    joined = client.post(f"/v1/join/{token}", json={"display_name": "Casey"}).json()
    participant_id = joined["participant"]["id"]

    resp = client.delete(f"/v1/sessions/{live_session_id}/participants/{participant_id}", headers=owner_headers)
    assert resp.status_code == 204

    session = client.get(f"/v1/sessions/{live_session_id}", headers=owner_headers).json()
    assert participant_id not in {p["id"] for p in session["participants"]}


def test_removing_unknown_participant_is_not_found(client, owner_headers, live_session_id):
    resp = client.delete(f"/v1/sessions/{live_session_id}/participants/prt_missing", headers=owner_headers)
    assert resp.status_code == 404


def test_candidate_cannot_remove_participants(client, owner_headers, live_session_id):
    link = client.post(f"/v1/sessions/{live_session_id}/guest-links", headers=owner_headers, json={}).json()
    token = link["url"].rsplit("/", 1)[-1]
    joined = client.post(f"/v1/join/{token}", json={"display_name": "Casey"}).json()
    guest_headers = {"Authorization": f"Bearer {joined['collaboration_token']}"}

    resp = client.delete(
        f"/v1/sessions/{live_session_id}/participants/{joined['participant']['id']}",
        headers=guest_headers,
    )
    assert resp.status_code == 403

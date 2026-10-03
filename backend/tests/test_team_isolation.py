def test_cross_team_access_is_forbidden(client, seed_data):
    """
    Critical Correctness 6: Resource-Level Team Boundary Isolation
    A user from Team A (even a Manager of Team A) must not be able to view,
    modify, or query work items belonging to Team B without membership.
    """
    item_b = seed_data["item_b_assigned"]  # belongs to Team B
    token_mem_a = seed_data["tokens"]["mem_a1"]
    token_mgr_a = seed_data["tokens"]["mgr_a"]
    token_admin = seed_data["tokens"]["admin"]

    # 1. Team A Member attempting to GET Team B work item -> 403 Forbidden
    resp_mem = client.get(
        f"/api/work-items/{item_b.id}",
        headers={"Authorization": f"Bearer {token_mem_a}"}
    )
    assert resp_mem.status_code == 403
    assert resp_mem.json()["code"] == "TEAM_ACCESS_DENIED"

    # 2. Team A Manager attempting to GET Team B work item -> 403 Forbidden
    resp_mgr = client.get(
        f"/api/work-items/{item_b.id}",
        headers={"Authorization": f"Bearer {token_mgr_a}"}
    )
    assert resp_mgr.status_code == 403
    assert resp_mgr.json()["code"] == "TEAM_ACCESS_DENIED"

    # 3. Team A Manager attempting to PATCH Team B work item -> 403 Forbidden
    resp_patch = client.patch(
        f"/api/work-items/{item_b.id}",
        json={"version": item_b.version, "status": "RESOLVED"},
        headers={"Authorization": f"Bearer {token_mgr_a}"}
    )
    assert resp_patch.status_code == 403
    assert resp_patch.json()["code"] == "TEAM_ACCESS_DENIED"

    # 4. Global Admin CAN view Team B work item
    resp_admin = client.get(
        f"/api/work-items/{item_b.id}",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["id"] == item_b.id

def test_team_filtering_prevents_unauthorized_team_query(client, seed_data):
    """
    Querying GET /api/work-items?team_id=<Team B> as a Team A member returns 403.
    """
    team_b_id = seed_data["team_b"].id
    token_mem_a = seed_data["tokens"]["mem_a1"]

    resp = client.get(
        f"/api/work-items?team_id={team_b_id}",
        headers={"Authorization": f"Bearer {token_mem_a}"}
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TEAM_ACCESS_DENIED"

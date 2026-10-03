from app.models.activity import ActivityLog

def test_important_changes_create_activity_records(client, seed_data, db_session):
    """
    Critical Correctness 5: Transactional Activity History
    Mutations (creation, assignment, status change, priority change)
    must atomically create ActivityLog entries in the same transaction.
    """
    token = seed_data["tokens"]["mgr_a"]
    team_id = seed_data["team_a"].id
    member_id = seed_data["mem_a1"].id

    # 1. Create work item
    create_resp = client.post(
        "/api/work-items",
        json={
            "title": "Transactional Audit Verification",
            "description": "Ensure activity log is generated upon creation",
            "priority": "MEDIUM",
            "team_id": team_id
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert create_resp.status_code == 201
    item = create_resp.json()
    item_id = item["id"]
    version = item["version"]

    # 2. Assign item first (so IN_PROGRESS has an assignee)
    assign_resp = client.post(
        f"/api/work-items/{item_id}/assign",
        json={"version": version, "assignee_id": member_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert assign_resp.status_code == 200
    version = assign_resp.json()["version"]

    # 3. Change status to IN_PROGRESS
    status_resp = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert status_resp.status_code == 200
    version = status_resp.json()["version"]

    # 4. Change priority
    prio_resp = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "priority": "URGENT"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert prio_resp.status_code == 200
    version = prio_resp.json()["version"]

    # 5. Fetch activity log API
    activity_resp = client.get(
        f"/api/work-items/{item_id}/activity",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert activity_resp.status_code == 200
    logs = activity_resp.json()
    actions = [log["action"] for log in logs]

    assert "CREATED" in actions
    assert "STATUS_CHANGED" in actions
    assert "PRIORITY_CHANGED" in actions
    assert "ASSIGNED" in actions

    # Verify specific log details
    status_log = next(l for l in logs if l["action"] == "STATUS_CHANGED")
    assert status_log["old_value"] == "OPEN"
    assert status_log["new_value"] == "IN_PROGRESS"

    prio_log = next(l for l in logs if l["action"] == "PRIORITY_CHANGED")
    assert prio_log["old_value"] == "MEDIUM"
    assert prio_log["new_value"] == "URGENT"

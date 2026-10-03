import pytest

def test_member_cannot_change_priority_returns_403(client, seed_data):
    """
    Critical Correctness 4: Role-Based Server-Side Authorization
    A MEMBER belongs to the team, but cannot change priority of an item.
    Only MANAGER or ADMIN can change priority.
    """
    item = seed_data["item_a_unassigned"]
    token_member = seed_data["tokens"]["mem_a1"]

    resp = client.patch(
        f"/api/work-items/{item.id}",
        json={"version": item.version, "priority": "URGENT"},
        headers={"Authorization": f"Bearer {token_member}"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["code"] == "INSUFFICIENT_PERMISSIONS"

def test_member_cannot_assign_item_to_others_returns_403(client, seed_data):
    """
    MEMBER cannot arbitrarily assign tasks to other teammates.
    Only MANAGER or ADMIN can assign tasks to teammates.
    """
    item = seed_data["item_a_unassigned"]
    token_member = seed_data["tokens"]["mem_a1"]
    other_member_id = seed_data["mem_a2"].id

    resp = client.post(
        f"/api/work-items/{item.id}/assign",
        json={"version": item.version, "assignee_id": other_member_id},
        headers={"Authorization": f"Bearer {token_member}"}
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "INSUFFICIENT_PERMISSIONS"

def test_manager_can_change_priority_and_assign(client, seed_data):
    """
    MANAGER has authority within their team to adjust priority and assign members.
    """
    item = seed_data["item_a_unassigned"]
    token_manager = seed_data["tokens"]["mgr_a"]
    member_id = seed_data["mem_a1"].id

    # Manager changes priority
    resp_prio = client.patch(
        f"/api/work-items/{item.id}",
        json={"version": item.version, "priority": "HIGH"},
        headers={"Authorization": f"Bearer {token_manager}"}
    )
    assert resp_prio.status_code == 200
    new_version = resp_prio.json()["version"]
    assert resp_prio.json()["priority"] == "HIGH"

    # Manager assigns to member
    resp_assign = client.post(
        f"/api/work-items/{item.id}/assign",
        json={"version": new_version, "assignee_id": member_id},
        headers={"Authorization": f"Bearer {token_manager}"}
    )
    assert resp_assign.status_code == 200
    assert resp_assign.json()["assignee_id"] == member_id

import pytest
from app.models.work_item import WorkItem

def test_stale_work_item_update_returns_409_conflict(client, seed_data, db_session):
    """
    Critical Correctness 2: Optimistic Concurrency Control
    User A reads version = 1.
    User B modifies work item, incrementing version to 2.
    User A attempts to update using stale version = 1.
    Backend must reject with 409 Conflict and code VERSION_CONFLICT.
    """
    item_id = seed_data["item_a_unassigned"].id
    token_mgr = seed_data["tokens"]["mgr_a"]
    token_mem = seed_data["tokens"]["mem_a1"]

    # Initial state
    read_resp = client.get(
        f"/api/work-items/{item_id}",
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert read_resp.status_code == 200
    stale_version = read_resp.json()["version"]

    # User B updates priority from MEDIUM to HIGH
    update_b = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": stale_version, "priority": "HIGH"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert update_b.status_code == 200
    assert update_b.json()["version"] == stale_version + 1
    assert update_b.json()["priority"] == "HIGH"

    # User A (Manager from another tab/session) now tries to update description using the stale version
    update_a = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": stale_version, "description": "Overwriting from stale tab"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert update_a.status_code == 409
    error_payload = update_a.json()
    assert error_payload["code"] == "VERSION_CONFLICT"
    assert "modified by another user" in error_payload["message"].lower()

    # Verify database state was NOT overwritten by stale request
    db_session.rollback()
    item = db_session.query(WorkItem).filter(WorkItem.id == item_id).first()
    assert item.description != "Overwriting from stale tab"
    assert item.version == stale_version + 1

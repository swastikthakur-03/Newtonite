import pytest
from app.models.work_item import WorkItem

def test_concurrent_claiming_prevents_duplicate_claims(client, seed_data, db_session):
    """
    Critical Correctness 1: Two users attempt to claim the same unassigned work item.
    Only one must succeed (200 OK); the second must be rejected with 409 Conflict.
    The work item must not end up in an ambiguous state or double-assigned.
    """
    item_id = seed_data["item_a_unassigned"].id
    token_user_1 = seed_data["tokens"]["mem_a1"]
    token_user_2 = seed_data["tokens"]["mem_a2"]

    # Both read the same initial state (version = 1)
    read_resp = client.get(
        f"/api/work-items/{item_id}",
        headers={"Authorization": f"Bearer {token_user_1}"}
    )
    assert read_resp.status_code == 200
    initial_version = read_resp.json()["version"]
    assert read_resp.json()["assignee_id"] is None

    # First user claims successfully
    resp_1 = client.post(
        f"/api/work-items/{item_id}/claim",
        json={"version": initial_version},
        headers={"Authorization": f"Bearer {token_user_1}"}
    )
    assert resp_1.status_code == 200
    data_1 = resp_1.json()
    assert data_1["assignee_id"] == seed_data["mem_a1"].id
    assert data_1["version"] == initial_version + 1

    # Second user attempts to claim with the stale version (or while already claimed)
    resp_2 = client.post(
        f"/api/work-items/{item_id}/claim",
        json={"version": initial_version},
        headers={"Authorization": f"Bearer {token_user_2}"}
    )
    assert resp_2.status_code == 409
    data_2 = resp_2.json()
    assert data_2["code"] in ["ALREADY_ASSIGNED", "VERSION_CONFLICT"]

    # Even if User 2 reads the new version (version = 2), claiming is rejected because it is already assigned
    resp_3 = client.post(
        f"/api/work-items/{item_id}/claim",
        json={"version": data_1["version"]},
        headers={"Authorization": f"Bearer {token_user_2}"}
    )
    assert resp_3.status_code == 409
    assert resp_3.json()["code"] == "ALREADY_ASSIGNED"

    # Verify final database state remains strictly owned by User 1
    db_session.rollback()
    final_item = db_session.query(WorkItem).filter(WorkItem.id == item_id).first()
    assert final_item.assignee_id == seed_data["mem_a1"].id

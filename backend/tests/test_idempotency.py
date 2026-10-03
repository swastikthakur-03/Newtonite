import uuid
from app.models.work_item import WorkItem

def test_idempotent_work_item_creation_prevents_duplicates(client, seed_data, db_session):
    """
    Critical Correctness 3: Idempotency Protection
    Client issues POST /api/work-items with Idempotency-Key header.
    Network flakes or client retries with the same key.
    The backend returns the exact cached original response without inserting duplicate records.
    """
    token = seed_data["tokens"]["mgr_a"]
    team_id = seed_data["team_a"].id
    idempotency_key = f"key-{uuid.uuid4()}"

    payload = {
        "title": "Idempotent Payment Investigation",
        "description": "Double debit flagged on transaction #7899",
        "priority": "HIGH",
        "team_id": team_id
    }

    # Count work items before
    initial_count = db_session.query(WorkItem).filter(WorkItem.team_id == team_id).count()

    # First request
    resp_1 = client.post(
        "/api/work-items",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key
        }
    )
    assert resp_1.status_code == 201
    created_item = resp_1.json()
    item_id = created_item["id"]
    assert created_item["title"] == payload["title"]

    # Verify count increased by 1
    assert db_session.query(WorkItem).filter(WorkItem.team_id == team_id).count() == initial_count + 1

    # Retry the exact request with the same Idempotency-Key header
    resp_2 = client.post(
        "/api/work-items",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key
        }
    )
    assert resp_2.status_code in [200, 201]
    retried_item = resp_2.json()

    # Must return the SAME item ID and data
    assert retried_item["id"] == item_id
    assert retried_item["title"] == payload["title"]

    # Verify NO duplicate row was created in the database
    assert db_session.query(WorkItem).filter(WorkItem.team_id == team_id).count() == initial_count + 1

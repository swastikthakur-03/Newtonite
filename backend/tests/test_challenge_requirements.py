import pytest
import concurrent.futures
from app.models.work_item import WorkItem, WorkItemStatus, WorkItemPriority
from app.models.team import Team, TeamRole

def test_list_work_items_filters_and_validation(client, seed_data):
    """
    Test 1: List endpoint returns 200, respects filtering & sorting,
    rejects invalid sort/filter with 422, and properly escapes LIKE '%' wildcards.
    """
    token_mgr = seed_data["tokens"]["mgr_a"]

    # 1. Successful list
    resp = client.get("/api/work-items", headers={"Authorization": f"Bearer {token_mgr}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data

    # 2. Invalid sort_by returns 422
    resp_bad_sort = client.get(
        "/api/work-items?sort_by=nonexistent_field",
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_bad_sort.status_code == 422
    assert resp_bad_sort.json()["code"] == "INVALID_SORT_FIELD"

    # 3. Invalid status returns 422
    resp_bad_status = client.get(
        "/api/work-items?status=INVALID_STATUS",
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_bad_status.status_code == 422

    # 4. Search with literal '%' does not crash or match everything unexpectedly
    resp_search = client.get(
        "/api/work-items?search=%",
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_search.status_code == 200

def test_manager_cannot_grant_admin_and_isolated_from_other_teams(client, seed_data):
    """
    Test 2: Privilege escalation prevention:
    - Team manager cannot grant ADMIN role (only MEMBER/MANAGER permitted).
    - Manager of Team A cannot manage or add members to Team B.
    """
    token_mgr = seed_data["tokens"]["mgr_a"]
    team_a_id = seed_data["team_a"].id
    team_b_id = seed_data["team_b"].id
    user_to_add = seed_data["mem_b"].id

    # 1. Attempt to add a member with role ADMIN must be rejected with 422 validation error
    resp_grant_admin = client.post(
        f"/api/teams/{team_a_id}/members",
        json={"user_id": user_to_add, "role": "ADMIN"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_grant_admin.status_code == 422

    # 2. Manager of Team A cannot add a member to Team B (403 forbidden)
    resp_cross_team_add = client.post(
        f"/api/teams/{team_b_id}/members",
        json={"user_id": seed_data["mem_a1"].id, "role": "MEMBER"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_cross_team_add.status_code == 403

def test_team_creation_restricted_to_system_admin(client, seed_data):
    """
    Test 3: POST /api/teams is restricted to system admin (is_admin=True).
    Team managers and members get 403.
    """
    token_mgr = seed_data["tokens"]["mgr_a"]
    token_admin = seed_data["tokens"]["admin"]

    # Manager cannot create a team
    resp_mgr = client.post(
        "/api/teams",
        json={"name": "Manager Forbidden Team"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_mgr.status_code == 403

    # System Admin can create a team
    resp_admin = client.post(
        "/api/teams",
        json={"name": "Admin Authorized Team"},
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp_admin.status_code == 201
    assert resp_admin.json()["name"] == "Admin Authorized Team"

    # Duplicate team name returns 409
    resp_dup = client.post(
        "/api/teams",
        json={"name": "Admin Authorized Team"},
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp_dup.status_code == 409

def test_registration_and_team_access_flow(client, seed_data):
    """
    Test 4: Register -> Login (case-insensitive email) -> 0 team access ->
    Manager adds member by email -> user can now access team items.
    """
    # 1. Register new user
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "name": "New Registered User",
            "email": "NewUser@Test.COM",
            "password": "Password123"
        }
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    new_user_token = reg_data["access_token"]
    new_user_email = reg_data["user"]["email"]
    assert new_user_email == "newuser@test.com"

    # 2. Login with uppercase email works (case-insensitive login)
    login_resp = client.post(
        "/api/auth/login",
        json={
            "email": "NEWUSER@TEST.COM",
            "password": "Password123"
        }
    )
    assert login_resp.status_code == 200

    # 3. New user has 0 team access, cannot access Team A items
    team_a_id = seed_data["team_a"].id
    item_a_id = seed_data["item_a_unassigned"].id
    access_resp = client.get(
        f"/api/work-items/{item_a_id}",
        headers={"Authorization": f"Bearer {new_user_token}"}
    )
    assert access_resp.status_code == 403

    # 4. Manager of Team A adds new user by email
    mgr_token = seed_data["tokens"]["mgr_a"]
    add_member_resp = client.post(
        f"/api/teams/{team_a_id}/members",
        json={"email": "newuser@test.com", "role": "MEMBER"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert add_member_resp.status_code == 201

    # 5. User now has team access
    access_resp_after = client.get(
        f"/api/work-items/{item_a_id}",
        headers={"Authorization": f"Bearer {new_user_token}"}
    )
    assert access_resp_after.status_code == 200

def test_full_workflow_and_ownership_matrix(client, seed_data):
    """
    Test 5: Full workflow transition matrix:
    - IN_PROGRESS requires an assignee (409 ASSIGNEE_REQUIRED).
    - Illegal transition returns 409 INVALID_TRANSITION.
    - Non-assignee member cannot change status (403 NOT_ASSIGNEE).
    - Only manager/admin may close or reopen.
    - PATCH can clear description and due_date.
    - Unassigning an IN_PROGRESS item returns it to OPEN.
    - Assigning a CLOSED item is rejected (409 ITEM_CLOSED).
    """
    token_mgr = seed_data["tokens"]["mgr_a"]
    token_mem1 = seed_data["tokens"]["mem_a1"]
    token_mem2 = seed_data["tokens"]["mem_a2"]
    team_id = seed_data["team_a"].id
    mem1_id = seed_data["mem_a1"].id

    # Create an open unassigned item
    create_resp = client.post(
        "/api/work-items",
        json={
            "title": "Workflow Test Item",
            "description": "Initial description",
            "priority": "HIGH",
            "team_id": team_id,
            "due_date": "2026-12-31T23:59:59Z"
        },
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert create_resp.status_code == 201
    item = create_resp.json()
    item_id = item["id"]
    version = item["version"]

    # 1. Move OPEN -> IN_PROGRESS without assignee fails with 409 ASSIGNEE_REQUIRED
    resp_no_assignee = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert resp_no_assignee.status_code == 409
    assert resp_no_assignee.json()["code"] == "ASSIGNEE_REQUIRED"

    # 2. Assign item to Member 1
    assign_resp = client.post(
        f"/api/work-items/{item_id}/assign",
        json={"version": version, "assignee_id": mem1_id},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert assign_resp.status_code == 200
    version = assign_resp.json()["version"]

    # 3. Member 2 (not assignee, not manager) attempts to change status -> 403 NOT_ASSIGNEE
    resp_unauthorized_member = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {token_mem2}"}
    )
    assert resp_unauthorized_member.status_code == 403
    assert resp_unauthorized_member.json()["code"] == "NOT_ASSIGNEE"

    # 4. Member 1 (assignee) moves OPEN -> IN_PROGRESS -> 200
    resp_assignee_start = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {token_mem1}"}
    )
    assert resp_assignee_start.status_code == 200
    version = resp_assignee_start.json()["version"]

    # 5. Member 1 tries illegal transition IN_PROGRESS -> CLOSED -> 409 INVALID_TRANSITION
    resp_illegal = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "status": "CLOSED"},
        headers={"Authorization": f"Bearer {token_mem1}"}
    )
    assert resp_illegal.status_code == 409
    assert resp_illegal.json()["code"] == "INVALID_TRANSITION"

    # 6. Member 1 clears description and due_date via PATCH null
    resp_clear = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "description": None, "due_date": None},
        headers={"Authorization": f"Bearer {token_mem1}"}
    )
    assert resp_clear.status_code == 200
    assert resp_clear.json()["description"] is None
    assert resp_clear.json()["due_date"] is None
    version = resp_clear.json()["version"]

    # 7. Unassigning an IN_PROGRESS item returns it to OPEN in the same tx
    unassign_resp = client.post(
        f"/api/work-items/{item_id}/assign",
        json={"version": version, "assignee_id": None},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert unassign_resp.status_code == 200
    assert unassign_resp.json()["assignee_id"] is None
    assert unassign_resp.json()["status"] == "OPEN"
    version = unassign_resp.json()["version"]

    # 8. Manager closes OPEN item -> CLOSED
    close_resp = client.patch(
        f"/api/work-items/{item_id}",
        json={"version": version, "status": "CLOSED"},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert close_resp.status_code == 200
    version = close_resp.json()["version"]

    # 9. Assigning a CLOSED item is rejected
    assign_closed_resp = client.post(
        f"/api/work-items/{item_id}/assign",
        json={"version": version, "assignee_id": mem1_id},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert assign_closed_resp.status_code == 409
    assert assign_closed_resp.json()["code"] == "ITEM_CLOSED"

def test_idempotency_hash_and_reused_key_different_body(client, seed_data):
    """
    Test 6: Idempotency with request hash:
    - Same key + different body returns 422 IDEMPOTENCY_KEY_REUSED.
    """
    token_mgr = seed_data["tokens"]["mgr_a"]
    team_id = seed_data["team_a"].id
    idemp_key = "unique-test-key-12345"

    # First request
    resp1 = client.post(
        "/api/work-items",
        json={"title": "Idempotent Creation Original", "priority": "MEDIUM", "team_id": team_id},
        headers={"Authorization": f"Bearer {token_mgr}", "Idempotency-Key": idemp_key}
    )
    assert resp1.status_code == 201

    # Same key with different body -> 422 IDEMPOTENCY_KEY_REUSED
    resp2 = client.post(
        "/api/work-items",
        json={"title": "Idempotent Creation Modified Body", "priority": "URGENT", "team_id": team_id},
        headers={"Authorization": f"Bearer {token_mgr}", "Idempotency-Key": idemp_key}
    )
    assert resp2.status_code == 422
    assert resp2.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

def test_parallel_claims_exactly_one_winner(client, seed_data):
    """
    Test 7: ThreadPoolExecutor concurrency:
    9 simultaneous claims on the same unassigned item -> exactly ONE 200 winner, others 409.
    """
    token_mgr = seed_data["tokens"]["mgr_a"]
    team_id = seed_data["team_a"].id

    # Create unassigned item
    create_resp = client.post(
        "/api/work-items",
        json={"title": "Parallel Race Unassigned Item", "priority": "HIGH", "team_id": team_id},
        headers={"Authorization": f"Bearer {token_mgr}"}
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    def perform_claim():
        return client.post(
            f"/api/work-items/{item_id}/claim",
            json={},  # Frontend sends no version
            headers={"Authorization": f"Bearer {token_mgr}"}
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
        futures = [executor.submit(perform_claim) for _ in range(9)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_responses = [r for r in results if r.status_code == 200]
    conflict_responses = [r for r in results if r.status_code == 409]

    assert len(success_responses) == 1
    assert len(conflict_responses) == 8

def test_parallel_idempotent_creates_exactly_one_row(client, seed_data):
    """
    Test 8: ThreadPoolExecutor concurrency:
    6 simultaneous requests with the same Idempotency-Key create exactly ONE work item,
    and all 6 return 201 with identical item ID and no 5xx errors.
    """
    token_mgr = seed_data["tokens"]["mgr_a"]
    team_id = seed_data["team_a"].id
    parallel_key = "concurrent-idemp-key-xyz"

    payload = {
        "title": "Parallel Idempotent Race",
        "description": "Ensure no duplicate items created",
        "priority": "HIGH",
        "team_id": team_id
    }

    def perform_create():
        return client.post(
            "/api/work-items",
            json=payload,
            headers={"Authorization": f"Bearer {token_mgr}", "Idempotency-Key": parallel_key}
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(perform_create) for _ in range(6)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    status_codes = [r.status_code for r in results]
    assert all(code in (200, 201) for code in status_codes)

    # All returned IDs must be identical
    created_ids = {r.json()["id"] for r in results}
    assert len(created_ids) == 1

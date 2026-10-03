# Engineering Decisions — Operations Under Pressure

This document details the core architectural and engineering decisions made during the design and implementation of the Newtonite Operations Management system. Each decision reflects deliberate trade-offs optimized for **correctness, operational clarity, maintainability, and business value**.

---

## 1. Why PostgreSQL?

### Context & Problem
Operations management systems require strict data integrity. When tickets, incident alerts, and operational tasks pass between teams, inconsistent state (e.g., duplicate assignments, orphaned activity records, partial status updates) directly degrades team trust and disrupts incident response.

### Decision
We chose PostgreSQL as the primary relational database.

### Technical & Business Rationale
1. **ACID Transactions**: Critical operational operations (such as updating a ticket status while simultaneously appending an audit record) require all-or-nothing transactional guarantees (`BEGIN ... COMMIT`).
2. **Atomic Row-Level Operations & Conditional Updates**: PostgreSQL supports atomic conditional `UPDATE` statements (`WHERE id = :id AND version = :version`), which allow us to implement robust optimistic concurrency control and race-condition-free claiming without distributed locks.
3. **Relational Integrity & Foreign Key Constraints**: Cascading rules (`ON DELETE CASCADE`, `ON DELETE SET NULL`) and unique constraints (`uq_team_user`, `uq_user_idempotency_key`) enforce business boundaries directly in the storage engine, preventing data corruption even in unexpected failure scenarios.
4. **Relational Querying, Indexing, and Filtering**: With multi-tenant team segregation, compound B-tree indexes on `(team_id, status)` and `(assignee_id, status)` allow fast index scans on tens of thousands of active work items without dedicated caching layers.

---

## 2. Why Optimistic Concurrency Control?

### Context & Problem
In high-pressure operations, multiple operators frequently view the same urgent work item simultaneously. 
If Operator A changes status from `OPEN` to `IN_PROGRESS`, while Operator B (viewing stale state from 10 minutes prior) updates the description or priority, a traditional naive `UPDATE` causes Operator B to silently overwrite Operator A's work ("the lost update problem").

### Decision
We implemented **Optimistic Concurrency Control (OCC)** using an integer `version` field on the `WorkItem` entity.

### Technical & Business Rationale
1. **Pessimistic vs. Optimistic Locking**:
   - *Pessimistic locking* (`SELECT ... FOR UPDATE` while a user opens a page) holds database locks during human think-time. This causes connection pool exhaustion, blocking read traffic, and potential deadlocks in web applications.
   - *Optimistic locking* assumes conflicts are occasional but detects them deterministically at the exact moment of mutation.
2. **Atomic SQL Execution**:
   Updates are executed atomically:
   ```sql
   UPDATE work_items
   SET title = :title,
       status = :status,
       priority = :priority,
       version = version + 1,
       updated_at = NOW()
   WHERE id = :id
     AND version = :expected_version;
   ```
   If `rowcount == 0`, the server rolls back and raises an explicit `409 Conflict` with error code `VERSION_CONFLICT`.
3. **User-Actionable UI**:
   The frontend translates this HTTP 409 into an alert banner:
   *"This work item was modified by another user. Please refresh before making changes."* with a one-click refresh button.

---

## 3. Why Transactional Activity Logs?

### Context & Problem
Operational failure investigations require answering:
- *Who changed this incident to BLOCKED?*
- *When was this payment investigation assigned to Rahul?*
- *What was the priority before it was marked URGENT?*

Without an auditable timeline, handoffs between shifts break down, and operators cannot reconstruct the evolution of a ticket.

### Decision
Every state mutation (creation, status update, priority change, claiming, reassignment) writes an `ActivityLog` entry **within the exact same database transaction** as the mutation.

### Technical & Business Rationale
1. **Atomicity Guarantee**:
   ```python
   # Inside work_item_service:
   db.execute(update_stmt)
   log_activity(db, work_item_id, actor_id, action="STATUS_CHANGED", old_value=old_status, new_value=new_status)
   db.commit()
   ```
   If the mutation fails, no log is written. If the log write fails, the mutation rolls back. We never end up with an unrecorded status change or a phantom log entry.
2. **Accountability & Shift Handoff**:
   Operators can review the chronological sequence of actions and comments, removing the ambiguity of chat logs and verbal handoffs.

---

## 4. Why Server-Side, Resource-Level Authorization?

### Context & Problem
Hiding buttons in the frontend provides zero security. An operator with browser devtools or direct curl access can easily issue a `PATCH /work-items/4` request.
Furthermore, simple role-based checks (e.g., "is user a MANAGER?") fail across teams: a Manager of Customer Operations should **not** have authority to mutate confidential tickets in Payments & Fraud.

### Decision
Authorization is enforced entirely **server-side at both the role level and the resource/team level**.

### Technical & Business Rationale
1. **Defense-in-Depth**:
   - The UI disables controls for UX clarity.
   - The FastAPI backend dependency `get_work_item_and_verify_access()` verifies that:
     1. The caller is authenticated via JWT.
     2. The caller belongs to the specific team owning the work item (or is a Global Admin).
     3. For sensitive operations (changing priority, reassigning teammates), the caller has the `MANAGER` or `ADMIN` role *within that team*.
2. **Cross-Team Resource Boundary Isolation**:
   Attempting to view or mutate another team's items returns an immediate `403 Forbidden` (`TEAM_ACCESS_DENIED`).
3. **Query Isolation**:
   All listing and dashboard endpoints enforce `filter(WorkItem.team_id.in_(user_team_ids))` on the database query, making it impossible to leak cross-team items in search results or pagination.

---

## 5. Security Architecture: `is_admin` vs Team Roles (Privilege Escalation Prevention)

### Context & Problem
Originally, `is_global_admin()` inspected whether a user had an `ADMIN` role in *any* team row. Concurrently, `POST /teams/{id}/members` accepted `role=ADMIN`. This created an immediate privilege escalation vulnerability: a team manager adding an admin to their local team inadvertently granted that user system-wide administrator privileges across all teams in the organization.

### Decision
1. Added `users.is_admin = Column(Boolean, default=False, nullable=False)` as the **single source of truth** for global administration.
2. Removed `ADMIN` from the `TeamRole` database enum (`MEMBER` and `MANAGER` only).
3. System administrators are seeded with `is_admin = True` and **no team membership rows**.
4. Effective permissions derive a virtual `"ADMIN"` role for global administrators, enabling them to inspect or manage all teams without polluting team membership rosters.
5. In the frontend, `isGlobalAdmin` strictly inspects `user.is_admin`.

### Technical & Business Rationale
- **Principle of Least Privilege**: Local team managers can only delegate roles up to `MANAGER` within their bounded scope.
- **Auditable Boundary**: Elevating an employee to system administrator is an explicit organization-level operation, not a side effect of team assignment.

---

## 6. Atomic Claiming Without Client-Supplied Version

### Context & Problem
When an unassigned work item appears in the queue, multiple operators may click "Claim" simultaneously. If the API requires the client to supply a `version`, high-latency clients or race conditions lead to spurious `VERSION_CONFLICT` errors rather than identifying the true race winner.

### Decision
1. Made `version` optional in `WorkItemClaim`. The frontend claim call sends no version.
2. The claim guard is executed via a single atomic SQL statement:
   ```sql
   UPDATE work_items
   SET assignee_id = :user_id,
       version = version + 1,
       updated_at = NOW()
   WHERE id = :id
     AND assignee_id IS NULL
     AND status NOT IN ('RESOLVED', 'CLOSED');
   ```
3. If `rowcount == 0`, the server re-reads the row with `populate_existing()` to diagnose and return the precise failure reason:
   - `ALREADY_ASSIGNED` (409) if another operator won the race.
   - `ITEM_NOT_CLAIMABLE` (409) if the ticket was resolved or closed.
   - `VERSION_CONFLICT` (409) if a version was explicitly provided and mismatched.

### Technical & Business Rationale
- **Zero Race Conditions**: Row-level locking during the PostgreSQL `UPDATE` guarantees that exactly one transaction succeeds, even under 9+ concurrent threads.
- **Accurate User Feedback**: Instead of generic errors, operators see exactly who claimed the item.

---

## 7. Idempotency Fingerprinting & Concurrent Request Races

### Context & Problem
Network retries (e.g. mobile reconnects or double-clicking form submit) can retransmit identical requests. Conversely, an attacker or buggy client could reuse an idempotency key with a mutated payload (e.g. creating an urgent item under a previously used key).

### Decision
1. Added `request_hash = Column(String(64), nullable=False)` storing the SHA-256 digest of the canonicalized request payload:
   `hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()`
2. If an existing `(user_id, key)` is encountered:
   - If `record.request_hash != incoming_hash`: Immediately reject with `422 IDEMPOTENCY_KEY_REUSED`.
   - If hash matches: Re-verify team access and return the stored payload with replay header.
3. If two simultaneous same-key requests hit the server, one succeeds and the other encounters a database `IntegrityError` on `uq_user_idempotency_key`. The loser catches `IntegrityError`, rolls back its transaction, and replays the winner's result.

---

## 8. Pagination Strategy: Offset Paging vs Keyset Paging

### Context & Problem
Operations management systems require browsing paginated queues.

### Decision
We implemented standard `limit` / `offset` pagination with `order_by(None).count()` for total count calculation and whitelisted sort fields (`updated_at`, `created_at`, `status`, `due_date`, `title`, `priority`).

### Technical & Business Rationale
- **Why Offset Paging at this Scale**: Operational queues for mid-level teams typically contain thousands to tens of thousands of items, partitioned by `team_id`. Offset paging with compound indexes (`(team_id, updated_at)`) executes in sub-millisecond times while allowing operators to jump directly to page numbers and see total record counts.
- **When to Migrate to Keyset Paging**: If operational history exceeds 500,000+ active items per team where deep offset traversal (`OFFSET 50000`) becomes expensive due to scanning skipped rows, the query should transition to keyset (cursor-based) pagination:
  `WHERE (team_id = :team_id) AND (updated_at, id) < (:last_updated_at, :last_id) ORDER BY updated_at DESC, id DESC LIMIT 20`.

---

## 9. What Was Intentionally Not Built?

In accordance with the one-day scope and the principle of building the **smallest coherent product that solves the business problem properly**, several features were deliberately omitted.

| Feature Intentionally Omitted | Alternative Implemented | Engineering & Business Trade-off |
| :--- | :--- | :--- |
| **Real-time WebSockets / SSE** | Short-interval polling on Dashboard + Optimistic Concurrency Conflict Banners (409) on stale edits. | WebSockets introduce stateful connection management, reconnect storms, sticky sessions, and horizontal scaling complications. For operational work items, optimistic concurrency gives 100% correctness with zero connection state complexity. |
| **Microservices & Event Buses (Kafka/RabbitMQ)** | Modular FastAPI monolith with SQLAlchemy domain services and direct DB transactions. | Microservices introduce distributed transactions, dual writes, eventual consistency lag, network latency, and deployment complexity that actively harm an internal operations system built by a single team. |
| **External Search Engine (Elasticsearch/OpenSearch)** | PostgreSQL B-tree indexing + ILIKE queries on indexed columns with pg_trgm GIN fallback. | Adding an external search cluster introduces data synchronization pipelines, out-of-sync indexes, and operational overhead. For tens of thousands of work items, PostgreSQL handles substring and filter indexing in single-digit milliseconds. |
| **External Distributed Idempotency Service (Redis)** | PostgreSQL-backed `idempotency_records` table with unique constraint on `(user_id, key)` and SHA-256 fingerprinting. | Redis introduces cache eviction policies and cache-to-DB split-brain concerns. Storing the idempotency key in PostgreSQL ensures the key record and the created entity share the exact same ACID transaction. |
| **Complex Workflow Engine / BPMN State Machine** | Strict transition matrix (`ALLOWED_TRANSITIONS`) enforced server-side. | Complex workflow engines add excessive configuration layers, complex migration paths, and rigidity. A clean transition matrix with role-checked rules solves 95% of operational coordination needs with total transparency. |
| **OAuth / SSO / MFA** | Standard JWT authentication with bcrypt password hashing and constant-time dummy verification for unknown users. | As specified by the challenge, avoiding external identity provider dependencies keeps setup frictionless, reproducible, and verifiable in an interview assessment without external API keys. |

---

## Summary

The Newtonite Operations Management system is designed around a single architectural philosophy:
> **Correctness and explicit failure modes in the database and service layer are vastly more valuable to business operations than architectural complexity.**

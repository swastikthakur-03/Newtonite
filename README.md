# Newtonite Operations Management — Operations Under Pressure

A robust, business-oriented internal operations management system built for the **Newtonite Software Engineering Challenge: "Operations Under Pressure"**.

Replaces disorganized spreadsheets, fragmented email threads, and lost chat conversations with a coherent, auditable operational tracking system centered around **Work Items**.

---

## 1. Project Overview & Business Problem

As companies scale, managing operational incidents, customer escalations, compliance investigations, and infrastructure tasks via chat and spreadsheets leads to systemic failures:
- **Lost Requests**: Work items get buried without clear status or visibility.
- **Ambiguous Ownership**: Two operators work on the same problem, or no one owns it.
- **Stale Updates & Overwriting**: An operator viewing outdated information overwrites recent fixes.
- **Lack of Traceability**: Incident post-mortems cannot determine who changed what or when.
- **Cross-Team Leakage**: Sensitive investigations are accessible to unauthorized teams.

This application provides the minimal, high-correctness solution to these problems with **strict server-side authorization, optimistic concurrency control, race-condition-free claiming, idempotent creation, and transactional activity history**.

---

## 2. System Architecture

```text
                     ┌────────────────────────────────────────┐
                     │          Next.js Frontend              │
                     │  (TypeScript, Tailwind, React Query)   │
                     └───────────────────┬────────────────────┘
                                         │
                               REST API / JSON
                           JWT Auth Bearer Token
                                         │
                     ┌───────────────────▼────────────────────┐
                     │          FastAPI Monolith              │
                     │                                        │
                     │  • JWT Authentication & Hashing        │
                     │  • Role & Resource Authorization       │
                     │  • Optimistic Concurrency Engine       │
                     │  • Atomic Claiming / Assigning         │
                     │  • Idempotency Header Engine           │
                     │  • Transactional Audit Logger          │
                     └───────────────────┬────────────────────┘
                                         │
                               SQLAlchemy / psycopg2
                                         │
                     ┌───────────────────▼────────────────────┐
                     │         PostgreSQL Database            │
                     │                                        │
                     │  • ACID Multi-Table Transactions       │
                     │  • Atomic Conditional UPDATEs          │
                     │  • Relational Foreign Key Cascades     │
                     │  • B-Tree Multi-Column Indexes         │
                     └────────────────────────────────────────┘
```

---

## 3. Technology Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, TanStack Query, React Hook Form, Lucide Icons.
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PyJWT, bcrypt.
- **Database**: PostgreSQL 18 (ACID transactions, row-level conditional updates).
- **Testing**: pytest, HTTPX, FastAPI TestClient.

---

## 4. Critical Correctness Guarantees

The application deliberately implements 4 non-trivial correctness patterns:

### A. Optimistic Concurrency Control (Stale Update Prevention)
- Each `WorkItem` maintains a monotonically increasing `version` integer.
- Updates execute atomic SQL conditional writes:
  ```sql
  UPDATE work_items
  SET ..., version = version + 1, updated_at = NOW()
  WHERE id = :id AND version = :expected_version;
  ```
- If another user updated the entity in the interim, the update returns `409 Conflict` (`VERSION_CONFLICT`).
- The frontend renders an interactive alert banner with a one-click **Refresh Latest State** button.

### B. Concurrent Claiming & Assignment
- Unassigned work items are claimed via atomic conditional update:
  ```sql
  UPDATE work_items
  SET assignee_id = :user_id, version = version + 1
  WHERE id = :id AND assignee_id IS NULL AND version = :version;
  ```
- If two users attempt to claim simultaneously, exactly one succeeds; the second receives `409 Conflict` (`ALREADY_ASSIGNED`), preventing dual ownership.

### C. Idempotency Protection
- `POST /api/work-items` accepts an optional `Idempotency-Key` header.
- Repeated requests with the same key for a user return the cached result with status code and body without creating duplicate database rows.

### D. Transactional Activity History
- All state changes (creation, status update, priority change, assignment, claim) write to `ActivityLog` in the **exact same database transaction** as the mutation. If one fails, both roll back.

### E. Resource-Level Cross-Team Authorization
- Roles: `MEMBER`, `MANAGER`, `ADMIN`.
- A manager of Team A cannot view or mutate Team B's work items unless they are a member of Team B or a Global Admin. Non-admins querying other teams receive `403 Forbidden` (`TEAM_ACCESS_DENIED`).

---

## 5. Demo Personas & Pre-Seeded Accounts

The database is seeded with realistic personas for testing different roles and team boundaries:

| Persona | Email | Password | Role | Team(s) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Alex Mercer** | `admin@newtonite.internal` | `password123` | **ADMIN** | System-Wide | Global authority across all teams and resources. |
| **Priya Sharma** | `priya.manager@newtonite.internal` | `password123` | **MANAGER** | Engineering Core | Can assign tasks, change priority, manage Engineering items. |
| **Rahul Verma** | `rahul.member@newtonite.internal` | `password123` | **MEMBER** | Engineering Core | Can claim unassigned work, update assigned status, comment. |
| **Swastik Roy** | `swastik.ops@newtonite.internal` | `password123` | **MANAGER** | Customer Operations | Manages operational escalations and compliance tickets. |
| **Ananya Patel** | `ananya.fraud@newtonite.internal` | `password123` | **MEMBER** | Payments & Fraud | Demonstrates cross-team isolation; cannot access Engineering Core items. |

> **Tip**: The login page provides quick one-click buttons for each persona for instant switching during evaluation!

---

## 6. Local Setup & Running Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL running locally (Default port `5433` or `5432`)

### 1. Database Configuration
The backend connects to PostgreSQL via `DATABASE_URL`:
```bash
# Default in app/core/config.py:
DATABASE_URL=postgresql+psycopg2://postgres@localhost:5433/newtonite_db
```
To create the development and testing databases in PostgreSQL:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" -U postgres -p 5433 newtonite_db
& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" -U postgres -p 5433 newtonite_test_db
```

### 2. Backend Setup
From the project root:
```powershell
# Activate Python virtual environment
.\backend\venv\Scripts\Activate.ps1

# (Optional) Install dependencies
pip install -r backend/requirements.txt

# Run database migrations
alembic -c alembic.ini upgrade head

# Seed initial demo data (users, teams, work items, audit history)
$env:PYTHONPATH = "backend"
python -m app.seed

# Start FastAPI backend server
uvicorn app.main:app --app-dir backend --reload --port 8000
```
Backend API will be accessible at `http://localhost:8000` with Swagger documentation at `http://localhost:8000/docs`.

### 3. Frontend Setup
From another terminal window:
```powershell
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```
Open your browser at `http://localhost:3000`.

---

## 7. Running Automated Tests

Run the complete test suite (all 17 test cases passing):
```powershell
.\scripts\run_tests.ps1
```
Or directly via pytest:
```powershell
$env:PYTHONPATH = "backend"
.\backend\venv\Scripts\pytest.exe -v
```

---

## 8. API Endpoint Reference

| Method | Endpoint | Description | Auth Required | Role / Boundary |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Self-registration (8-72 byte password, lowercase email) | No | Public (gated by `ALLOW_SELF_REGISTRATION`) |
| `POST` | `/api/auth/login` | Authenticate with email/password, returns JWT | No | Public |
| `GET` | `/api/auth/me` | Fetch authenticated user profile & memberships | Yes | Authenticated |
| `GET` | `/api/teams` | List accessible teams | Yes | Member of team or Admin |
| `POST` | `/api/teams` | Create operational team | Yes | System Admin only (`is_admin=True`) |
| `GET` | `/api/teams/{id}/members` | List members of a team | Yes | Member of team or Admin |
| `POST` | `/api/teams/{id}/members` | Add member by `email` or `user_id` (MEMBER/MANAGER) | Yes | Manager of team or Admin |
| `GET` | `/api/dashboard/stats` | Attention metrics (Urgent, Blocked, Assigned) | Yes | Member of team or Admin |
| `GET` | `/api/work-items` | Paginated, filtered search of work items | Yes | Filtered by team boundary |
| `POST` | `/api/work-items` | Create work item (accepts `Idempotency-Key`) | Yes | Member of target team |
| `GET` | `/api/work-items/{id}` | Fetch full work item details | Yes | Team access verified |
| `PATCH`| `/api/work-items/{id}` | Optimistic concurrency update (`version` req) | Yes | Member / Manager for priority |
| `POST` | `/api/work-items/{id}/claim` | Atomically claim unassigned item (no version req) | Yes | Member of team |
| `POST` | `/api/work-items/{id}/assign` | Reassign item (`version` required) | Yes | Manager or Admin of team |
| `GET` | `/api/work-items/{id}/comments` | Chronological comments list (limit/offset) | Yes | Team access verified |
| `POST` | `/api/work-items/{id}/comments` | Add comment & audit row in one transaction | Yes | Team access verified |
| `GET` | `/api/work-items/{id}/activity` | Chronological audit trail (limit/offset) | Yes | Team access verified |

---

## 9. Known Limitations

In keeping with the one-day scope, the following boundaries were intentionally observed:
- **No WebSockets / Live Push**: Relies on short-interval polling on the dashboard and optimistic locking on detail views.
- **No Dedicated Search Engine**: Relies on PostgreSQL B-tree indexes and ILIKE substring queries rather than Elasticsearch.
- **No Third-Party IdP**: Relies on self-contained JWT and bcrypt rather than Google OAuth/Okta/SAML.
- **No Complex BPMN Engine**: Uses standard enum states (`OPEN`, `IN_PROGRESS`, `BLOCKED`, `RESOLVED`, `CLOSED`) with service-layer validation.

For in-depth explanations of trade-offs, please see [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md).

# Clinic Booking API

A REST API for a small clinic (5 doctors, 30-minute slots) built with **Django + Django REST Framework + PostgreSQL**, deployed on **Render** through **GitHub Actions**.

> **Live URL:** `https://clinic-booking-api-b84r.onrender.com` &nbsp;·&nbsp; **Interactive docs:** `/docs/` &nbsp;·&nbsp; **Health:** `/health`
> *(replace after the first deploy; the free tier sleeps when idle, so the first request can take ~30-60 s)*
>
> **Demo data is synthetic.** Reviewer credentials are shared privately (see [Demo accounts](#demo-accounts)).

| Section | Where |
|---|---|
| 1. System design | [§1 below](#1-system-design) |
| 2. API implementation | [§2](#2-api-implementation) |
| 3. Deployment & CI/CD | [§3](#3-deployment--cicd) |
| 4. AI reflection | [`docs/AI_REFLECTION.md`](docs/AI_REFLECTION.md) |
| Legal / privacy (Kenya) | [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) |

---

## 1. System design

### 1.1 Why this is a health-data system, not just a booking system

A record of *which patient booked which doctor, and when* reveals health information. Under Kenya's **Data Protection Act 2019** health data is *sensitive personal data*, and the **Digital Health Act 2023** (with its regulations) adds sector duties. So the design starts from privacy and security constraints, and the booking logic sits inside them. The full mapping is in [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md); the design consequences are woven through the decisions below. *(I am an engineer, not a lawyer: legal points are design assumptions to be validated by counsel and the clinic's DPO.)*

### 1.2 Domain model

```mermaid
erDiagram
    DOCTOR ||--o{ WORKING_SCHEDULE : "works"
    DOCTOR ||--o{ APPOINTMENT : "sees"
    PATIENT ||--o{ APPOINTMENT : "books"
    USER   ||--o| PATIENT : "logs in as"
    USER   ||--o{ AUDIT_LOG : "acts"
    DOCTOR { int id PK; string full_name; string specialty; int slot_minutes; bool is_active }
    WORKING_SCHEDULE { int doctor_id FK; int weekday; time start_time; time end_time }
    PATIENT { uuid id PK; string full_name; string phone; string email; string guardian_name; datetime consent_given_at; string consent_notice_version; datetime anonymised_at }
    APPOINTMENT { uuid id PK; int doctor_id FK; uuid patient_id FK; datetime start_time; datetime end_time; string status; string cancel_reason_code; string cancel_note; int reschedule_count }
    AUDIT_LOG { uuid id PK; datetime created_at; int actor_id FK; string action; string object_type; string object_id; json metadata }
```

**Components** (Django apps, one responsibility each):

| App | Responsibility |
|---|---|
| `clinic` | Doctors, weekly working-hours blocks, **slot arithmetic** (pure functions, no I/O beyond reading the schedule) |
| `accounts` | Patients (minimal PII + consent evidence), registration, login, data-subject export, anonymisation |
| `appointments` | The booking **service layer** (`services.py`: book / cancel / reschedule / availability), endpoints, DB constraints |
| `audit` | Append-only log of who did what to which record (IDs only, never PII or free text) |
| `core` | Error envelope, health check, injectable clock (so time-dependent rules are testable) |

### 1.3 Key decisions and trade-offs

**D1 - Slots are *derived*, not stored.** Availability = (doctor's working blocks → 30-min grid) − (booked appointments). *Alternative:* pre-generate a `Slot` table per doctor per day. That makes "which slots are free" a simple query but needs a generator job, goes stale when schedules change, and creates rows nobody uses. At 5 doctors the computed approach is cheaper, always correct, and trivially cacheable later.

**D2 - The database guarantees no double booking.** A *partial unique constraint* on `(doctor, start_time) WHERE status = 'booked'` is the source of truth. The service does a friendly pre-check (to give a clear message) and then translates the constraint's `IntegrityError` into `409`. *Alternatives:* (a) check-then-insert in code - has a race window; (b) `SELECT … FOR UPDATE` on the doctor row - correct but serialises all of a doctor's bookings and still wants the constraint as a backstop; (c) `SERIALIZABLE` isolation - correct but needs retry plumbing. The constraint is the simplest thing that is correct under any concurrency, and it protects against future code paths (admin scripts, imports) that bypass the service. **Verified, not assumed:** the concurrency test fires 8 simultaneous bookings at one slot and asserts exactly one wins; I confirmed the test is meaningful by temporarily removing the constraint and the pre-check, after which all 8 "succeeded" and the test failed.

**D3 - Cancelling is a soft state change.** Cancelled rows are kept (audit, reporting, dispute resolution). Because the unique constraint only covers `booked` rows, cancelling frees the slot with *no extra code* - a cancelled row simply stops holding the slot. A patient may therefore have several cancelled rows for the same time, which is intended.

**D4 - Reschedule is an in-place atomic update**, not cancel+create. It keeps one appointment identity (links, reminders and history stay attached), runs in one transaction, applies *exactly the same validator as a fresh booking* (one function, so the paths cannot drift), and writes `from/to` times to the audit log. The old slot is freed in the same statement that claims the new one.

**D5 - Time.** Everything is stored in UTC; working hours are interpreted in `Africa/Nairobi` (EAT, no DST); responses are rendered with the `+03:00` offset. **Naive datetimes are rejected** (`400`) instead of guessed - guessing the zone of a medical appointment is how patients arrive three hours early.

**D6 - Identity and access.** The brief has no auth, but a bonus endpoint is `GET /patients/{id}/appointments`, which without access control is a textbook IDOR leaking health data. So: JWT login (15-min access tokens), roles *patient* and *staff*, patient/appointment IDs are **UUIDs**, and every object lookup is scoped to the caller. Anything you may not see returns **404, not 403**, so IDs can't be probed. `GET /doctors/{id}/availability` is public by design and exposes only *free* slots, never who holds the others.

**D7 - Data minimisation.** No national ID, no diagnosis, no "reason for visit". The one free-text field the spec requires (cancellation *reason*) can accidentally contain health details ("chemo clash"), so it is length-limited (200), stored, **never copied to logs or the audit trail**, and the UI is expected to offer preset reasons (an optional `reason_code` is accepted for that).

**D8 - Django admin is not installed.** It would be a second, broader PII-exposing surface. Staff act through the audited API.

**D9 - PostgreSQL over SQLite.** The partial-unique-constraint guarantee and the real concurrency test need a real database. (SQLite works as a zero-config dev fallback; the concurrency test skips there.)

**D10 - Modular monolith.** One deployable, clear internal boundaries. Microservices would add operational cost with no benefit for "5 doctors, starting small". The boundaries (`clinic` / `accounts` / `appointments` / `audit`) are where I'd cut first if needed.

### 1.4 Ambiguities I resolved (as the brief requested)

| # | Ambiguity | Decision |
|---|---|---|
| A1 | "Within working hours" | The *whole* 30-min slot must fit inside a working block, on the slot grid (09:15 is rejected, 16:30 is the last slot of a 17:00 close). Error message tells the user the doctor's actual hours. |
| A2 | Past / "within 1 hour" (bonus) | Past ⇒ `422 slot_in_past`. Lead time is configurable (`BOOKING_MIN_LEAD_MINUTES`, default 60): `< 60 min` is rejected, **exactly 60 min is allowed**. Availability hides slots inside the lead window so clients never offer an unbookable slot. |
| A3 | How far ahead | Max 90 days (`BOOKING_MAX_ADVANCE_DAYS`) - bounds enumeration and stale bookings. |
| A4 | Who is the patient on `POST /appointments`? | Patient users book for themselves (token identifies them). Staff must pass `patient_id`. A patient passing someone else's id gets `403`. |
| A5 | Cancel/reschedule an appointment that already started | `409 appointment_in_past` - history shouldn't be rewritten after the fact. |
| A6 | Reschedule scope | Same doctor, new time. Same-time → `422 same_slot`. Cancelled → `409 appointment_cancelled`. Changing doctor = cancel + new booking. |
| A7 | Same patient, two doctors, same time | Blocked (`409 patient_double_booked`) - a person can't be in two rooms. |
| A8 | Cancellation `reason` | Required free text (3-200 chars) as the brief says, plus optional `reason_code` enum for reporting. |
| A9 | Status codes | `400` malformed · `401/403` auth · `404` missing/not yours · `409` state conflict (taken, already cancelled) · `422` business-rule violation (outside hours, past, too soon). |
| A10 | Non-working day availability | `200` with `slots: []` (not an error). Past date → `422`. |
| A11 | Trailing slashes | Accepted either way (`/appointments` and `/appointments/`). |

### 1.5 Growth path ("we're starting small but want to grow")

Built now: per-doctor `slot_minutes`, multiple blocks per day (lunch breaks), indexed queries, stateless API (horizontally scalable), CI-enforced migrations.
Next, in the order I'd do them: `ScheduleException` (leave/holidays) → `Clinic` FK for multi-site → notifications via a queue (SMS/email reminders) → Redis for shared rate-limit counters and availability caching → read replica / reporting → interoperability with Kenya's national digital-health exchange (Digital Health Agency) once the clinic is certified.

---

## 2. API implementation

All errors share one envelope: `{"error": {"code": "slot_taken", "message": "...", "details": {}}}`.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /auth/register` | public (throttled) | Patient self-registration; **requires `consent: true`** |
| `POST /auth/token` · `/auth/token/refresh` | public (throttled) | JWT login / refresh |
| `GET /doctors` | public | List active doctors |
| `GET /doctors/{id}/availability?date=YYYY-MM-DD` | public | **Free** 30-min slots for that day |
| `POST /appointments` | patient/staff | **Book** a slot |
| `GET /appointments/{id}` | owner/staff | Read one |
| `PATCH /appointments/{id}/cancel` | owner/staff | **Cancel** with `reason`; slot becomes bookable again; `409` if already cancelled |
| `PATCH /appointments/{id}/reschedule` | owner/staff | **Move** to `start_time`; validated like a fresh booking; `409` if cancelled |
| `GET /patients/{id}/appointments` | owner/staff | *(bonus)* upcoming, soonest first |
| `GET /patients/{id}/export` | owner/staff | Data-subject access/portability (JSON) |
| `POST /patients` | staff | Register a walk-in patient (consent attested) |
| `GET /health` | public | Liveness + deployed commit |

```bash
# book (times must carry an offset)
curl -X POST $URL/appointments -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"doctor_id": 1, "start_time": "2026-11-03T09:00:00+03:00"}'
# cancel
curl -X PATCH $URL/appointments/$ID/cancel -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason": "Plans changed", "reason_code": "patient_request"}'
# reschedule
curl -X PATCH $URL/appointments/$ID/reschedule -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"start_time": "2026-11-04T10:00:00+03:00"}'
```

### Security controls in the code

JWT with short expiry · object-level authorisation (404 on foreign ids) · UUID ids · scoped throttling (`booking` 20/min, `auth` 10/min, plus anon/user defaults) · strict input validation (naive datetimes, enum codes, length limits) · generic registration error (no account-existence oracle) · password validators (min 10 chars) · no Django admin · `DEBUG` off by default and the app **refuses to boot** in production without `DJANGO_SECRET_KEY` · HTTPS redirect, HSTS (1 y, preload), secure cookies, `nosniff`, `X-Frame-Options: DENY` · JSON-only renderers · custom 404/500 handlers that leak no internals · logs never include request bodies · non-root container · CORS closed by default (no CORS middleware; add `django-cors-headers` with explicit origins when a browser frontend exists).

### Tests

`pytest` - 65 tests, ~94% coverage: validation rules and boundaries (exactly-1-hour lead, last slot, off-grid, lunch break, weekend, >90 days), conflict handling, cancel/reschedule state machine, access control (cross-patient 404s), privacy (no PII/free-text in audit log or availability), registration/consent, anonymisation, export, end-to-end JWT flow, and the **real-Postgres concurrency test**. Time is pinned via an injectable clock, so boundary tests are deterministic.

---

## 3. Deployment & CI/CD

- **Public URL:** `https://<your-service>.onrender.com`
- **Provider:** Render (Docker web service + managed PostgreSQL), defined in [`render.yaml`](render.yaml).
- **Branch that deploys:** **`main`**. Render's own auto-deploy is **off**; only the pipeline can deploy, so **nothing reaches production without passing the checks**.

### Pipeline ([`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml))

| Trigger | Jobs |
|---|---|
| **Every pull request** | `lint-and-security` (ruff, bandit, pip-audit) · `test` (Postgres service container; migration-drift check; pytest incl. concurrency test; ≥85% coverage gate) · `image` (docker build + Trivy HIGH/CRITICAL scan) |
| **Merge to `main`** | the same three jobs, then `deploy`: calls Render's deploy hook for *that exact commit SHA*, then polls `/health` until it reports the same SHA (smoke test). Fails the run if the new version is not live in 15 min. |

**One-time setup**

1. Push the repo to GitHub. In Render: *New → Blueprint →* select the repo (creates the DB + service). Set `DEMO_STAFF_PASSWORD` and `DEMO_PATIENT_PASSWORD` in the dashboard.
2. Render → service → *Settings → Deploy Hook*: copy the URL into a GitHub **secret** `RENDER_DEPLOY_HOOK_URL`; add a repo **variable** `APP_URL` (e.g. `https://clinic-booking-api.onrender.com`). Create a GitHub *Environment* named `production` (optionally with required reviewers).
3. GitHub → *Settings → Branches*: protect `main` - require a PR and the three status checks; no direct pushes.

**Rollback:** redeploy the previous commit from the Render dashboard (or `git revert` + merge). Migrations here are additive; destructive migrations should follow expand/contract.

**Operational notes / known limits:** migrations run on container start (fine for one instance; use a release job when scaling out) · rate-limit counters are per-process (move to Redis when scaling) · Render free tier sleeps when idle and its free Postgres expires after ~30 days.

---

## Running locally

```bash
# Option A - Docker (API + Postgres, demo data seeded)
docker compose up --build            # http://localhost:8000/docs/

# Option B - Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                 # then export the variables (or use direnv)
export DJANGO_DEBUG=true DATABASE_URL=postgres://clinic:clinic@localhost:5432/clinic
python manage.py migrate && python manage.py seed_demo
python manage.py runserver

pytest                                # needs PostgreSQL for the concurrency test (skips on SQLite)
ruff check . && ruff format --check . && bandit -q -r apps config -x "*/tests/*"
```

### Demo accounts

`seed_demo` creates 5 fictional doctors and two logins - `reception@demo.clinic.test` (staff) and `patient@demo.clinic.test` (patient). Passwords come from `DEMO_STAFF_PASSWORD` / `DEMO_PATIENT_PASSWORD` (or are generated and printed once), so **no credentials live in this repository**. Use `/auth/token` with `{"username": "<email>", "password": "..."}`.

### Operations

`python manage.py anonymise_patient <uuid>` handles an erasure request (identity removed, future bookings cancelled, history kept).

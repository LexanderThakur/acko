# Design.md — How Contract Guard is built

The architecture, data model, algorithms and key decisions behind the system.
Companion docs: `Plan.md` (what/why), `Decisions.md` (comparison rules), `Progress.md` (status).

---

## 1. Architecture at a glance

```
        Browser (React SPA, JWT in localStorage)
              │  /api/...  (same origin)
              ▼
        nginx  ── static dist/ + SPA fallback
              │      /api, /docs proxied
              ▼
        gunicorn → Django (DRF, function-based views)
              │
              ├─ base/views/        HTTP layer: auth, services, specs, comparisons,
              │                     consumers, publishing, webhooks, health
              ├─ base/services/     pure logic, no HTTP:
              │     spec_parser.py  · YAML/JSON → validated OpenAPI → $ref-expanded contract
              │     differ.py       · contract A vs B → change dicts
              │     impact.py       · breaking changes × consumer declarations
              │     notify.py       · webhook POST (never fatal)
              ├─ base/serializers/  explicit request/response shapes
              └─ SQLite (volume)    13 models, Django ORM
```

Layer rules:

- **Views** are thin: validate → call a service → persist → respond. No business logic.
- **Services** are pure and testable: they take plain dicts/objects, return dicts/lists.
  They never touch `request`.
- **Serializers** are written explicitly (no field-guessing ModelSerializers) so the
  Swagger schema is predictable and the UI can rely on field names.
- Everything runs **in-process** (NFR-01): no Celery, no Redis, no queues. Diffing a full
  kit spec pair is milliseconds; webhooks are 5-second-timeout POSTs from the request path
  but *recorded, never blocking* (a down receiver cannot fail a publish).

---

## 2. Data model (13 models)

```
Service 1──* SpecVersion ──(partial unique: one published per service)
Service 1──* ConsumerUse *──1 APIConsumer
ConsumerUse 1──* FieldDependency (sends|reads + field_path)

SpecVersion *──1 APIComparison (base_version) *──1 SpecVersion (target_version)
APIComparison 1──* APIChange (path, method, field_path, side, change_type, severity,
                             breaking, explanation, old_value, new_value)
APIComparison 1──* ImpactReport 1──* ImpactItem (change, consumer, reason)

Service 1──* PublishingAttempt (spec_version, status, comparison?, impact_report?,
                                decided_by?, decided_at, comment)
PublishingAttempt 1──* Notification (payload JSON, receiver_url, delivered, response_status)
WebhookEvent (received payloads of the built-in receiver)
```

Design choices worth knowing:

| Choice | Why |
| --- | --- |
| `SpecVersion.version` is **not unique** per service | Re-publishing an existing version number with different content is exactly the unsafe act we must detect (kit's claims-api trap). Identity = upload row, not the label. |
| **Partial unique constraint** `unique_published_spec_per_service` | Enforces "one published version at a time" at the DB level (NFR-02), not just in app code. |
| Raw `spec` text **and** expanded `contract` stored side by side | The raw text is the source of truth for humans; the contract is the precomputed input for the differ. `$ref` expansion at upload time means re-organizing schema files between versions is invisible (non-breaking) — the diff compares meaning, not layout. |
| `APIChange` stores `path`, `method`, `field_path` **separately** | Impact analysis joins changes against `ConsumerUse` + `FieldDependency` rows with exact SQL-friendly fields; a merged "location" string would need parsing at join time. The human-readable `location` is a derived property. |
| `APIChange.side` (request/response/none) | Encodes the sends↔request / reads↔response matching rule as data, so impact is a straight filter. |
| `old_value` / `new_value` JSON snapshots on each change | The comparison detail page can show exactly what moved without re-diffing. |
| `PublishingAttempt.comparison/impact_report` nullable FKs | The first version of a service has no base to diff against — it's auto-approved with `comparison = null`. |
| `Notification` records delivery outcome | FR-10's auditability: every payload, its receiver URL, whether it was delivered, and the HTTP status. |
| `WebhookEvent` as a separate model | The built-in receiver is just another endpoint of the same app; received payloads are stored so the Notifications page can show "what an external system would have received". |

Status enums (`models.TextChoices`):

- `SpecStatus`: `draft` → `published` | `blocked` (draft with a blocked attempt)
- `AttemptStatus`: `blocked` / `approved` / `rejected`
- `ChangeSeverity`: `blocker` / `major` / `minor` / `info` — `breaking = severity ∈ {blocker, major}`
- `ChangeSide`: `request` / `response` / `none`
- `ChangeType`: 12 values (`endpoint_removed`, `path_added`, `method_removed/added`,
  `field_removed/added`, `field_type_changed`, `required_added/removed`,
  `path_param_changed`, `response_removed`, `metadata_changed`)

---

## 3. The spec pipeline (FR-01, FR-02)

`spec_parser.py` — upload → normalized contract:

1. **Parse**: YAML or JSON (PyYAML safe-load), must be a mapping.
2. **Validate**: `openapi` field must start with `3.0` (OpenAPI 3.0.x), `info.version` present.
3. **Expand `$ref`s**: only local refs (`#/components/...`), resolved recursively with
   JSON-Pointer escaping (`~1` → `/`, `~0` → `~`), depth-guarded (max 64) against cycles.
4. Errors raise `SpecParseError` with a plain message → the view returns 400.

Rejected at the gate: invalid YAML, wrong OpenAPI version, missing `info.version`,
broken refs. **A spec that can't parse can never enter the registry**, which keeps the
differ simple (it only ever sees resolved, valid contracts).

---

## 4. The differ (FR-03, FR-04)

`differ.py` — two resolved contracts → list of change dicts.

**Matching strategy**

1. **Endpoints** are keyed by *normalized path template*: every `{param}` becomes `{}`,
   so `/quotes/{id}` and `/quotes/{quoteId}` are the same endpoint. A rename therefore
   produces **one** `path_param_changed` blocker instead of an endpoint-removed +
   endpoint-added pair.
2. Within a matched endpoint, **methods** are matched by name.
3. Within a matched operation: path parameters by name (or paired by position when
   renamed), then metadata, request body (`application/json` only), and per-response-code
   schemas.
4. **Schemas** are diffed recursively: object → `required` lists + `properties`;
   array → `items` with `[]` appended to the field path; scalars → type comparison.
5. **Field paths** accumulate as `premium.breakdown[].amount` (dots + `[]`), matching
   the consumer-declaration notation exactly.

**Classification** — every rule lands in one of four severities (full catalog with
worked examples in `Decisions.md`):

- BLOCKER: endpoint/method removed, field removed, type changed, path param changed
- MAJOR: required added on request (common fields), response status removed,
  new required request field
- MINOR: field added (or made optional), endpoint/method added
- INFO: summary/description, `deprecated`, `x-sunset` markers

A refinement worth noting: **required-added/removed only fires for fields present in
both versions**. A brand-new required request field is reported once as
`field_added (required)` MAJOR — not twice as field-added + required-added.

Output is deterministic and sorted **blockers → majors → minors → infos** (stable within
severity by path/field), so list views never need re-sorting and tests are stable.

---

## 5. Impact analysis (FR-06)

`impact.py` — the static join, no runtime probing:

```
for change in comparison.changes.filter(breaking=True):
    direction = request → sends | response → reads | none → (any, endpoint-level)
    for use in ConsumerUse where provider_service == base_version.service:
        match if normalize_path(use.path) == normalize_path(change.path)
               and (change.method empty or use.method == change.method)
        endpoint-level change (no field_path) → consumer affected, done
        else → affected if any FieldDependency of the use where
               direction matches AND field paths overlap
```

**Field-path overlap** is bidirectional prefix matching: removing `premium.breakdown`
affects a consumer that reads `premium.breakdown[].amount`; removing `premium` affects
one that reads `premium.total`. Segment boundaries are respected (`premium.breakdown[]`
does not match `premium.breakdownCustomer`).

Results are persisted as an `ImpactReport` + one `ImpactItem` per (change, consumer) —
deduplicated — each with a generated human-readable reason (NFR-07), e.g.:
*"declares GET /quotes/{id} (reads premium.breakdown[].amount) — field ... was removed
from response 200 of GET /quotes/{id}"*.

---

## 6. The publishing gate (FR-07, FR-08)

`publishing_views.py` — the state machine:

```
POST /api/publishing-attempts/ {spec_version_id}
        │
        ├─ version already published?            → 400
        ├─ pick base version:
        │     latest earlier upload, published preferred (never a newer version)
        ├─ no base? (first version ever)          → auto-APPROVED, becomes published
        ├─ base exists:
        │     get-or-create Comparison (reuse if identical pair already run)
        │     run impact analysis
        │     affected consumers == 0             → auto-APPROVED, becomes published
        │     affected consumers ≥ 1              → BLOCKED, spec stays draft,
        │                                          published version untouched
        └─ notification fired on every terminal state (approved / blocked)

POST .../{id}/approve/   (only blocked attempts; 400 otherwise)
      → approved, decided_by/decided_at/comment stamped, version becomes published
        (previous published version demoted to draft)

POST .../{id}/reject/    (only blocked attempts; 400 otherwise)
      → rejected, version returns to draft, published version untouched
```

Invariants:

- **Atomicity**: the decision + status flips happen in one transaction.
- **Idempotent history**: attempts are append-only; approve/reject mutate exactly one
  blocked attempt, guarded by status check + 400.
- **The published pointer never regresses**: only approve/auto-approve changes it;
  reject and blocked do nothing to it (NFR-02).
- `_publish()` swaps the published version: demote others, set this one — respecting the
  partial unique constraint.

---

## 7. Notifications (FR-10)

`notify.py` + `webhook_views.py` — self-contained by default:

- Every terminal attempt state fires a JSON payload:
  `{event, service, version, attempt_id, status, blocked_reasons[], affected_consumers[]}`
  with events `publish.approved` / `publish.blocked` / `publish.rejected`.
- **Receiver resolution**: `WEBHOOK_RECEIVER_URL` env var if set, else the server's own
  built-in receiver (`request.build_absolute_uri("/api/webhook-events/receive/")`), so the
  whole system needs no second process. Over the compose network the self-URL uses the
  `backend` hostname.
- **Delivery is fire-and-record**: 5 s timeout, any failure is stored on the
  `Notification` row (`delivered=false`), never raised. A dead receiver cannot fail,
  delay, or roll back a publishing decision.
- The built-in receiver accepts any JSON POST unauthenticated (like an external receiver
  would be), stores it as a `WebhookEvent`, and the Notifications page renders them.

---

## 8. Auth (NFR-04)

- simplejwt with **access token only** (8 h lifetime, no refresh flow) — deliberate
  product simplification: "when it expires, log in again".
- Endpoints: `POST /api/auth/register/` (password-validated, dup-username → 400),
  `POST /api/auth/login/` (`{access}` only), `GET /api/auth/me/`.
- `JWTAuthentication` is the default authentication class; every view is `IsAuthenticated`
  except: register/login, `GET /api/health/`, and the webhook receiver (which must accept
  external-style calls).
- The React app attaches `Authorization: Bearer` via an axios request interceptor and
  clears the token + redirects on any 401.

---

## 9. API conventions

- All routes under `/api/`, JSON, function-based views with `@api_view` (project rule —
  no class-based/Generic views).
- Dispatching FBVs (e.g. `services` handles GET list + POST create) are documented with
  `extend_schema_view` — **lowercase method keys** (`get=`, `post=`), which is required
  for `@api_view` views (uppercase keys are silently ignored by drf-spectacular).
- Pagination: `PageNumberPagination`, page size 50, DRF-style envelopes
  (`{count, next, previous, results}`) — the UI unwraps `results ?? data` everywhere.
- Errors follow DRF conventions (`{field: [messages]}` or `{detail: "..."}`);
  the frontend's shared `errorMessage()` flattens them into one readable line.
- OpenAPI schema served at `/api/schema/`, interactive docs at `/docs/`.

---

## 10. Frontend design

- **React 19 + MUI v9 + react-router 7 + axios + Formik/Yup** (Vite).
- `src/api/client.js`: one axios instance, `baseURL: /api`; **request interceptor** injects
  the Bearer token from localStorage; **response interceptor** on 401 clears the token and
  hard-redirects to `/login` (loop-guarded).
- `src/auth/AuthContext.jsx`: register/login/logout + session restore via `/auth/me/`
  on first load; `Protected`/`GuestOnly` route guards in `App.jsx` with a spinner while
  the session resolves.
- Layout: AppBar + responsive drawer, `/services/:id`, `/comparisons/:id` nested routes.
- State: intentionally **no Redux/React Query** — each page fetches what it needs with
  `useEffect` + local state; the data volumes are tiny (NFR-01) and the refetch pattern
  (`load()` callback after mutations) keeps pages honest.
- MUI v9 note: `alignItems`/`justifyContent`/`flexWrap` are **not** system props on
  `Stack` anymore — they must go in `sx={{...}}` (25 occurrences were migrated during UI
  development; direct props leak to the DOM and are ignored).
- Severity/status chips share one component (`SeverityChip.jsx`) so the color vocabulary
  is consistent everywhere: blocker=error, major=warning, minor=info, approved/published=
  success.

---

## 11. Deployment design

- **Two images, alpine, multi-stage**: backend (`deps` builds a venv behind the
  `requirements.txt` cache boundary → runtime copies only `/opt/venv` + code; gunicorn,
  CMD migrates then `exec`s gunicorn as PID 1); frontend (`npm ci` behind the manifest
  cache boundary → `vite build` → `nginx:alpine` serves `dist/` + proxies `/api`).
- **docker-compose**: nginx :5173 → gunicorn :8000 (compose DNS name `backend`);
  SQLite on the `sqlite_data` volume (`SQLITE_DIR`); backend healthcheck hits
  `/api/health/`; frontend `depends_on: service_healthy`.
- **Config by env**: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
  `SQLITE_DIR`, `WEBHOOK_RECEIVER_URL` — dev defaults keep `manage.py runserver` working
  with zero env setup.
- **Migrate-on-start**: idempotent `manage.py migrate --noinput` in the container CMD, so
  `docker compose up --build` after a model change applies it automatically.
- **Scaling story (MVP)**: one gunicorn process with 2 workers/2 threads is plenty at MVP
  data size. SQLite + single node is the accepted constraint; moving to Postgres means
  swapping the `DATABASES` engine — no other code assumes SQLite.

---

## 12. Known limitations (deliberate MVP scope)

Documented so nobody assumes they're bugs — all listed in `Decisions.md` §7:

- No enum/format/constraint-narrowing detection; `allOf`/`oneOf` compared as-is.
- Only `application/json` bodies/responses; query/header params ignored (path params only).
- Webhook delivery is synchronous fire-and-record (no retry queue) — acceptable at MVP
  scale because delivery outcome is recorded and the receiver is ours by default.
- Single-instance deployment (SQLite); no multi-node story yet.
- The React pages refetch instead of using a query cache — fine at this data size, would
  be the first thing to introduce if the registry grows.

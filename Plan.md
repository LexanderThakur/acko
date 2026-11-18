# Contract Guard — Plan (MVP)

## 1. Problem Statement

Modern software systems consist of multiple services that communicate through APIs. Teams develop and maintain these services independently.

When a team modifies an API — renaming a field, changing a data type, making a parameter mandatory, or removing an endpoint — other services that depend on that API may stop working.

Teams lack visibility into **who consumes their APIs** and **whether a proposed change will break them**.

**Contract Guard** is a centralized API contract registry where teams:

1. register their services and upload versions of their OpenAPI specifications,
2. register the consumers of their APIs (down to the fields they read and send),
3. get automatic comparison between spec versions, with breaking changes flagged,
4. see which consumers are affected by each change,
5. and cannot publish an unsafe version without review — with a webhook notification fired so the owning team finds out immediately.

### MVP scope note

We build the **functional requirements** end-to-end on SQLite, with a minimal UI on top of the API. Non-functional requirements below are kept as design constraints, not separate workstreams.

---

## 2. Functional Requirements (MVP focus)

| ID | Requirement | MVP notes |
| --- | --- | --- |
| FR-01 | **Service Registry** — register services (name, owner team, description); upload specs as YAML or JSON; parse and validate them | Validation = parses as OpenAPI 3.0.3 and has `info.version` |
| FR-02 | **Shared Components** — resolve internal `$ref`s so comparison works on the real contract, not file layout | Local refs only (`#/components/...`) |
| FR-03 | **Version Comparison** — diff two spec versions: endpoints, methods, parameters, request/response schemas, field types, required fields, status codes | See change catalog below |
| FR-04 | **Change Classification** — each change is breaking or not, with a severity and a plain-English explanation | `BLOCKER` / `MAJOR` = breaking, `MINOR` / `INFO` = non-breaking |
| FR-05 | **Consumer Registry** — register consumers with per-endpoint `sends` and `reads` field paths | Field paths: dots for nesting, `[]` for list items |
| FR-06 | **Impact Analysis** — given a comparison, list the consumers affected and which change affects them | Match on method + path + field path |
| FR-07 | **Publishing Workflow** — attempt to publish a version; if breaking changes affect consumers, the attempt is **blocked** until someone approves; approving publishes the version | No affected-consumer breakage ⇒ publishes immediately |
| FR-08 | **Changelog & History** — comparisons, their changes, and every publishing attempt are stored and queryable | Read-only list endpoints |
| FR-09 | **Dashboard** — pages showing services, versions, changes, affected consumers, publishing status, impact reports | Server-rendered Django templates are enough |
| FR-10 | **Notifications & Metrics** — every publish attempt (blocked or approved) POSTs a JSON notification to the webhook receiver; a metrics endpoint summarizes the system | Receiver: `http://localhost:9900` |

### FR-03 change catalog (MVP detection rules)

| Change | Severity |
| --- | --- |
| Endpoint (path) removed | BLOCKER |
| Method removed from endpoint | BLOCKER |
| Request/response field removed or renamed | BLOCKER |
| Field type changed | BLOCKER |
| New field added to `required` (request) | MAJOR |
| Path parameter renamed or made differently typed | BLOCKER |
| Response status code removed | MAJOR |
| Optional request/response field added | MINOR |
| Field made optional (`required` removed) | MINOR |
| Description/summary/`x-*` metadata changes | INFO |

MVP simplification: compare **one service at a time**, versions paired by our own registry (not by file name). `$ref`s are expanded before diffing, so moving schemas between components is invisible (non-breaking).

### FR-06 impact rule (MVP)

A consumer is affected when, for at least one breaking change:

- the consumer declares a use with the same **provider**, **method** and **path** (path parameters matched as `{name}` placeholders), and
- the consumer `reads` (response changes) or `sends` (request changes) a field matching the changed field path.

Sends↔request-side changes, reads↔response-side changes.

---

## 3. Non-Functional Requirements (design constraints)

| ID | Requirement |
| --- | --- |
| NFR-01 | Spec validation, comparison and impact analysis run in-process and finish in seconds at MVP data size |
| NFR-02 | A failed or blocked publish attempt never mutates the currently published version |
| NFR-03 | FK integrity: services → spec versions, consumers → field dependencies, comparisons → changes, attempts → notifications |
| NFR-04 | JWT auth on all mutating endpoints; only authenticated users may modify services, specs and publish |
| NFR-05 | Parsing, diffing, classification, impact and notification live in separate modules (`services/`, `diff/`, `impact/`, `notify/`) |
| NFR-06 | Plain Django/DRF patterns; no assumptions that cap team/service counts |
| NFR-07 | Every change and block carries a human-readable explanation |
| NFR-08 | `pip install -r requirements.txt && python manage.py migrate && python manage.py runserver` runs the app; seed kit data with one management command |

---

## 4. Core Entities (SQLite via Django ORM)

| Entity | Key fields | Notes |
| --- | --- | --- |
| **User** | Django built-in | JWT auth |
| **Service** | `name` (unique), `owner_team`, `description` | A provider microservice |
| **SpecVersion** | `service` FK, `version`, `spec` (raw YAML/JSON text), `status` (`draft` / `published` / `blocked`), `created_at` | One `published` per service at a time |
| **APIConsumer** | `name` (unique), `team` | A consuming service |
| **ConsumerUse** | `consumer` FK, `provider_service` FK, `method`, `path` | One endpoint the consumer calls |
| **FieldDependency** | `use` FK, `direction` (`sends` / `reads`), `field_path` | Field-level dependency |
| **APIComparison** | `base_version` FK, `target_version` FK, `created_at` | One diff run |
| **APIChange** | `comparison` FK, `location` (method + path), `change_type`, `severity`, `breaking` (bool), `explanation`, `old_value`, `new_value` | Detected change |
| **ImpactReport** | `comparison` FK, `created_at` | One impact run per comparison |
| **ImpactItem** | `report` FK, `change` FK, `consumer` FK, `reason` | Which change hits which consumer |
| **PublishingAttempt** | `service` FK, `spec_version` FK, `status` (`blocked` / `approved` / `rejected`), `decided_by` FK, `decided_at`, `comment`, `created_at` | The publish gate |
| **Notification** | `attempt` FK, `payload` (JSON), `receiver_url`, `delivered` (bool), `response_status`, `created_at` | Webhook delivery record |

---

## 5. API Contract (MVP)

Base URL: `/api/` — JSON, JWT auth (`POST /api/auth/token/` with `{username, password}` → `{access, refresh}`), all mutating endpoints require a Bearer token.

### Services & specs (FR-01, FR-02)

| Method & path | Body / params | Response |
| --- | --- | --- |
| `GET /api/services/` | — | `[{id, name, owner_team, description, published_version}]` |
| `POST /api/services/` | `{name, owner_team, description}` | `201 {id, ...}` |
| `GET /api/services/{id}/specs/` | — | `[{id, version, status, created_at}]` |
| `POST /api/services/{id}/specs/` | raw YAML/JSON body (or multipart `file=`) | `201 {id, version, status: "draft"}` · `400` if not valid OpenAPI |

A spec is parsed at upload; internal `$ref`s are expanded and the normalized contract stored alongside the raw text (FR-02).

### Comparisons & changes (FR-03, FR-04, FR-08)

| Method & path | Body | Response |
| --- | --- | --- |
| `POST /api/comparisons/` | `{base_spec_id, target_spec_id}` | `201 {id, base_version, target_version, summary: {blocker, major, minor, info}}` |
| `GET /api/comparisons/` | — | list |
| `GET /api/comparisons/{id}/` | — | comparison + `changes: [{location, change_type, severity, breaking, explanation, old_value, new_value}]` |
| `GET /api/comparisons/{id}/impact/` | — | `{report_id, affected_consumers: [{consumer, team, reason, change}]}` (runs impact analysis, FR-06) |

### Consumers (FR-05)

| Method & path | Body | Response |
| --- | --- | --- |
| `GET /api/consumers/` | — | `[{id, name, team, uses: [{provider, method, path, sends[], reads[]}]}]` |
| `POST /api/consumers/` | `{name, team, uses: [...]}` (kit-shaped YAML/JSON accepted) | `201` |
| `GET /api/consumers/{id}/` · `DELETE` | — | detail / remove |

### Publishing workflow (FR-07, FR-08)

| Method & path | Body | Response |
| --- | --- | --- |
| `POST /api/publishing-attempts/` | `{spec_version_id}` | `201 {id, status}` — status is `"approved"` (published) if no breaking change affects a consumer, else `"blocked"` |
| `GET /api/publishing-attempts/` | — | list with outcomes (history) |
| `POST /api/publishing-attempts/{id}/approve/` | `{comment?}` | `{id, status: "approved"}` — spec version becomes `published` (FR-07) |
| `POST /api/publishing-attempts/{id}/reject/` | `{comment}` | `{id, status: "rejected"}` — published version untouched (NFR-02) |

A blocked attempt fires a webhook (below) and leaves the currently published version unchanged.

### Notifications & metrics (FR-10)

| Method & path | Purpose |
| --- | --- |
| webhook `POST {receiver}/contract-guard` on every attempt | Body: `{event: "publish.blocked"\|"publish.approved", service, version, blocked_reasons: [...], affected_consumers: [...]}` |
| `GET /api/notifications/` | delivery records |
| `GET /api/metrics/` | `{services, spec_versions, comparisons, breaking_changes, blocked_attempts, affected_consumers}` |

### Dashboard (FR-09)

Server-rendered pages (Django templates, no SPA): services list → service detail (versions, published status) → comparison view (changes color-coded by severity) → impact view (affected consumers) → publish attempts log. Reads the same data as the API above.

---

## 6. Seeding & running (NFR-08)

- `python manage.py import_kit <path-to-contract-guard-starter-kit>` — registers the 3 kit services, uploads their 4 spec versions each (in order), loads the 4 consumers with their `uses`, and produces the comparisons. Powers the demo against the kit data read-only.
- Run: `python manage.py migrate && python manage.py runserver` + `docker compose up` for the webhook receiver (port 9900).
- Kit rules respected: files under `specs/` and `consumers/` are never modified.

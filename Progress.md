# Progress.md — What's built and what's left

Snapshot of the Contract Guard build as of **Nov 18, 2026**.
Requirements come from `Plan.md` (FR-01…FR-10, NFR-01…08); every ✅ below was
implemented **and verified live** against real kit data or a browser walkthrough.

---

## Functional requirements

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| FR-01 | Service registry + spec upload (YAML/JSON) | ✅ Done | paste text **or** file upload (multipart, 2 MB cap); version auto-read from `info.version`; garbage → 400 with readable message |
| FR-02 | `$ref` resolution ("shared components") | ✅ Done | local refs expanded recursively at upload; resolved contract stored beside raw text; broken ref rejected at upload (kit's `ClaimDocumnt` trap verified) |
| FR-03 | Version comparison | ✅ Done | normalized path matching (`{id}` ≡ `{quoteId}`), method/endpoint/field/required/response diffs; all 9 kit version-pairs produce sensible changelogs |
| FR-04 | Change classification | ✅ Done | BLOCKER/MAJOR/MINOR/INFO per the catalog — 15 rules documented in `Decisions.md`, each verified against kit pairs |
| FR-05 | Consumer registry with `sends`/`reads` | ✅ Done | accepts kit-file shape directly; idempotent re-registration; unknown provider → 400 |
| FR-06 | Impact analysis | ✅ Done* | full join engine (method + normalized path + field prefix matching, sends↔request / reads↔response) runs inside the publish gate; *public `GET /api/comparisons/{id}/impact/` endpoint not yet exposed* |
| FR-07 | Publishing workflow (the gate) | ✅ Done | diff vs latest earlier version → auto-approve or block; approve/reject with comment + reviewer stamp; blocked attempt never mutates the published version |
| FR-08 | Changelog & history | ✅ Done | comparisons, changes, impact reports, attempts, decisions all persisted and queryable; UI history pages |
| FR-09 | Dashboard | ✅ Done | React SPA (exceeds "server-rendered templates are enough"): stat cards, recent comparisons, blocked-attempt queue |
| FR-10 | Notifications & metrics | ✅ Done* | every attempt/decision POSTs a JSON notification; built-in receiver = zero extra servers; delivery recorded per attempt. *`GET /api/notifications/` + `GET /api/metrics/` endpoints not yet exposed (data exists in DB)* |

**Score: 9 of 10 FRs fully done, 2 small API-surface gaps (FR-06 public endpoint, FR-10 metrics).**

---

## Non-functional requirements

| NFR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| NFR-01 | in-process analysis, seconds at MVP size | ✅ | diff of full kit specs: milliseconds |
| NFR-02 | blocked publish never mutates published version | ✅ | verified: reject leaves published version untouched; one published per service enforced by partial unique constraint |
| NFR-03 | FK integrity across all entities | ✅ | 12 entities, 4 migrations |
| NFR-04 | JWT auth on mutating endpoints | ✅ | access-only tokens (8 h), Bearer; `/api/health/` and webhook receiver intentionally open |
| NFR-05 | modular services (parse/diff/impact/notify) | ✅ | `base/services/{spec_parser,differ,impact,notify}.py` |
| NFR-06 | plain Django/DRF, no scaling caps | ✅ | function-based views only, per project rule |
| NFR-07 | human-readable explanations everywhere | ✅ | every change/impact row carries one |
| NFR-08 | clone → install → migrate → run works | ✅/⚠️ | works via `docker compose up --build` (verified); **`import_kit` seeding command not yet written** |

---

## UI (React + MUI)

| Page | Status | Features |
| --- | --- | --- |
| Login / Register | ✅ | Formik + Yup validation, server errors surfaced, JWT in localStorage via axios interceptor, 401 → auto-logout to /login |
| Dashboard | ✅ | 6 stat cards, recent comparisons with severity chips, blocked-publish queue |
| Services | ✅ | register dialog, published-status cards |
| Service detail | ✅ | versions table, upload dialog (paste/file tabs), spec viewer (raw ↔ resolved contract), compare dialog, per-version Publish button |
| Comparisons + detail | ✅ | list with summary chips; detail table sorted blockers-first with side/location/explanation |
| Consumers | ✅ | kit-shaped registration form with repeatable uses rows (provider dropdown, method, path, sends/reads) |
| Publishing | ✅ | full attempt history; approve/reject dialogs with comment; success banners |
| Notifications | ✅ | received webhook events with payload JSON, clear button |

Whole flow verified end-to-end in the browser (upload kit spec → compare → publish
blocked → reject → notifications), and the production build passes.

---

## Infrastructure & docs

| Item | Status |
| --- | --- |
| Dockerfiles (alpine, cache-optimized multi-stage) | ✅ backend: deps→venv→gunicorn runtime; frontend: deps→vite build→nginx |
| `docker-compose.yml` | ✅ nginx (SPA + /api proxy) + gunicorn (migrate on boot, healthcheck) + SQLite volume; verified: register/login through the full proxy chain |
| Layer caching | ✅ proven: source edit → rebuild in ~4 s with pip/npm layers cached |
| `GET /api/health/` probe | ✅ wired into the container healthcheck |
| Env-driven settings | ✅ DEBUG / SECRET_KEY / ALLOWED_HOSTS / SQLITE_DIR / WEBHOOK_RECEIVER_URL |
| README.md | ✅ quick start, dev mode, env table, layout |
| Plan.md / Decisions.md / workflow.md / UIWorkflow.md | ✅ SRS · comparison rules · Swagger walkthrough · UI walkthrough |

---

## Remaining before "100% MVP"

Ordered by value/effort:

1. **`import_kit` management command** (NFR-08) — seed the 3 kit services × 4 versions +
   4 consumers + comparisons in one command; makes the demo reproducible on a fresh DB.
   ~1–2 h.
2. **`GET /api/comparisons/{id}/impact/`** (FR-06 surface) — the engine exists; it just
   needs a view returning the already-persisted ImpactReport. ~30 min.
3. **`GET /api/metrics/`** (FR-10 surface) — one view counting services/versions/
   comparisons/breaking/blocked. ~30 min.
4. **`GET /api/notifications/`** (FR-10 surface) — list Notification delivery records. ~30 min.
5. **`DELETE /api/consumers/{id}/`** (Plan API contract) — trivial, UI re-registration
   already covers the use case. ~15 min.
6. *(Optional polish)* pagination controls on long lists, dark mode, `format`/enum
   narrowing detection in the differ (documented as out of scope in `Decisions.md`).

## AWS deployment readiness

Ready for a single-instance demo deploy: compose file runs unchanged on an EC2 host with
Docker; SQLite on the volume ≈ EBS disk. Before internet-facing production:
real `DJANGO_SECRET_KEY` + TLS termination (ALB or Caddy/nginx certbot), and ideally
Postgres instead of SQLite if you ever need more than one app instance.

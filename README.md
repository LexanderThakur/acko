# Contract Guard

**A centralized API contract registry that stops teams from breaking each other's APIs.**

Modern systems are many services talking over APIs, built by independent teams. When one team
renames a field, changes a type, makes a parameter mandatory or removes an endpoint, every
service that depends on that API may stop working — and nobody finds out until production does.

Contract Guard is a registry where teams:

1. **register their services** and upload versions of their OpenAPI 3.0 specifications,
2. **register their consumers** — down to the fields they send and read on every endpoint,
3. get **automatic version comparison** with every change classified by severity,
4. see **which consumers are affected** by each breaking change,
5. and **cannot publish an unsafe version without review** — every publish decision fires a
   webhook notification.

The whole check is **static**: specs and consumer declarations are analyzed as data. Nothing
is ever probed at runtime.

---

## What's inside

| Piece | Tech | Where |
| --- | --- | --- |
| API backend | Django + DRF, JWT auth (access token), SQLite, Swagger via drf-spectacular | `backend/` |
| Web UI | React + MUI, axios (JWT interceptor), react-router | `frontend/` |
| Diff engine | `$ref` expansion, normalized path matching, severity catalog | `backend/base/services/differ.py` |
| Impact engine | joins breaking changes × consumer declarations | `backend/base/services/impact.py` |
| Publish gate | auto-approve / block / approve / reject + notifications | `backend/base/views/publishing_views.py` |

Docs that live in this repo:

- **`Plan.md`** — the SRS: requirements, entities, API contract
- **`Decisions.md`** — the exact rules used when comparing two versions (the severity catalog)
- **`workflow.md`** — paste-able walkthrough of every API endpoint in Swagger
- **`UIWorkflow.md`** — the same walkthrough for the React UI, as a worked example

---

## Quick start (Docker)

Prerequisite: [Docker](https://docs.docker.com/get-docker/) with Compose v2
(`docker compose version` should print something).

```bash
git clone <this-repo> contract-guard
cd contract-guard
docker compose up --build
```

That single command builds two images and starts the whole stack. First build takes a few
minutes (base images + dependencies); after that, source edits rebuild in seconds because
the dependency layers are cached.

When it's up:

| URL | What |
| --- | --- |
| **http://localhost:5173** | the web UI (start here) |
| http://localhost:5173/api/… | the API, proxied by nginx |
| http://localhost:8765/docs/ | Swagger UI for the raw API |
| http://localhost:8765/api/health/ | liveness probe (`{"ok": true}`) |

The database starts **empty** and lives in the `sqlite_data` volume, so your data survives
restarts and rebuilds.

### First 5 minutes in the UI

1. Open http://localhost:5173 → **Create an account** (any username, password ≥ 8 chars).
2. **Services → Register service** — e.g. `quote-api`, owner `Quotes team`.
3. On the service page, **Upload spec** — paste an OpenAPI 3.0 YAML (or upload a `.yaml`
   file). Upload two different versions of it.
4. **Compare versions** — pick base and target; every change shows with a severity
   (`blocker`/`major` are breaking).
5. **Consumers → Register consumer** — declare which endpoints it calls and which fields it
   sends/reads (`premium.breakdown[].amount` style paths).
6. Back on the service page, **Publish** a version:
   - no consumer affected → **auto-approved**, it becomes the published version;
   - a consumer is affected → **blocked**; go to **Publishing** and approve or reject it
     with a comment.
7. **Notifications** shows the webhook payloads every decision produced.

A full narrated tour (with real example data and what each screen should show) is in
**`UIWorkflow.md`**. Prefer testing the raw API? Follow **`workflow.md`** in Swagger.

### Starter kit data (optional)

`sde-startup-kit/contract-guard-starter-kit/` ships 3 example services × 4 spec versions
(`specs/`) and 4 consumer declarations (`consumers/`) including deliberate breaking changes
(renamed path parameters, removed fields, deprecations, a broken `$ref`). Upload these files
through the UI or Swagger to see the gate do its thing. The kit folder is read-only — the
app never writes there.

---

## Running without Docker (development)

Prerequisites: Python 3.12+, Node 20+.

**Backend**

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8765
# API on http://localhost:8765 — Swagger at /docs/
```

**Frontend** (new terminal)

```bash
cd frontend
npm install
npm run dev
# UI on http://localhost:5173 — Vite proxies /api to :8765
```

Environment variables (all optional in dev, see `docker-compose.yml` for production values):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | insecure dev key | set a real one in production |
| `DJANGO_DEBUG` | `1` | set `0` in production |
| `DJANGO_ALLOWED_HOSTS` | `""` | comma-separated hosts, e.g. `localhost,backend` |
| `SQLITE_DIR` | backend folder | put `db.sqlite3` elsewhere (Docker uses a volume) |
| `WEBHOOK_RECEIVER_URL` | built-in receiver | POST notifications to an external receiver instead |

---

## How the pieces fit

```
        ┌──────────────────────────── docker compose ────────────────────────────┐
        │                                                                        │
        │  :5173  nginx ─── serves the built React SPA (dist/)                   │
        │            │                                                           │
        │            └── /api/*, /docs/* ──proxy──►  :8000  gunicorn             │
        │                                              │        Django + DRF     │
        │                                              │        SQLite (volume)  │
        │                                              └── webhook POSTs to itself │
        └────────────────────────────────────────────────────────────────────────┘
```

- The SPA calls `/api/...` on its own origin; nginx forwards to the backend over the
  compose network — no CORS involved.
- Notifications default to the backend's **own built-in receiver**
  (`POST /api/webhook-events/receive/`), so no second service is needed; point
  `WEBHOOK_RECEIVER_URL` at an external receiver (chat/email gateway) to integrate one.
  The **Notifications** page shows what arrived either way.
- Publishing rule in one line: diff against the latest earlier version → if a breaking
  change touches a registered consumer's declared usage → **block** until a human
  approves; otherwise **auto-approve**. Details in `Decisions.md`.

---

## Useful commands

```bash
docker compose up -d          # start in the background
docker compose logs -f        # tail both services
docker compose ps             # status + health
docker compose restart        # restart (data persists)
docker compose down           # stop (data persists in the volume)
docker compose down -v        # stop and WIPE the database
docker compose build          # rebuild after code changes (cached, fast)
```

The backend healthcheck runs `manage.py migrate` on every start — idempotent, so model
changes are applied automatically on `docker compose up --build` after a pull.

---

## Project layout

```
.
├── docker-compose.yml        # the whole stack: nginx + gunicorn + volume
├── backend/                  # Django project (Dockerfile, requirements.txt)
│   ├── backend/              # settings / urls / wsgi
│   ├── base/                 # the app: models, views, serializers, services/
│   │   ├── services/         # differ.py · impact.py · spec_parser.py · notify.py
│   │   └── views/            # auth · services/specs · comparisons · consumers · publishing · webhooks
│   └── db.sqlite3            # (dev only; Docker keeps it on a volume)
├── frontend/                 # React + MUI SPA (Dockerfile, nginx.conf)
│   └── src/pages/            # Dashboard · Services · Comparisons · Consumers · Publishing · Notifications
├── sde-startup-kit/          # read-only starter kit: example specs + consumer files
├── Plan.md                   # SRS
├── Decisions.md              # comparison/severity rules
├── workflow.md               # Swagger walkthrough with paste-able bodies
└── UIWorkflow.md             # UI walkthrough with a worked example
```

# Contract Guard — Swagger UI Test Workflow

Step-by-step walkthrough of the APIs built so far. **Every step includes the exact request body to paste into Swagger's editor.**

**Setup:** `python manage.py runserver 8765` → open **http://localhost:8765/docs/**

Click **Try it out** on an endpoint → paste the body into the text field → **Execute**.
For authorized endpoints, click **Authorize** first and paste just the `access` token (Swagger adds `Bearer ` itself).

---

## Step 1 — Register a user

`POST /api/auth/register/` (no authorization needed)

**Paste:**

```json
{
  "username": "maya",
  "password": "Str0ng!passw0rd",
  "email": "maya@acko.com"
}
```

**Response 201:**

```json
{
  "id": 3,
  "username": "maya",
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

Copy `access` → **Authorize** → paste it (without the quotes). Already registered? Use Step 1b.

### 1b — Log in (existing user)

`POST /api/auth/login/`

**Paste:**

```json
{
  "username": "maya",
  "password": "Str0ng!passw0rd"
}
```

**Response 200:**

```json
{
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

## Step 2 — Register the service

`POST /api/services/` (authorized)

**Paste:**

```json
{
  "name": "quote-api",
  "owner_team": "Quotes team",
  "description": "Bike insurance quotes"
}
```

**Response 201:**

```json
{
  "id": 1,
  "name": "quote-api",
  "owner_team": "Quotes team",
  "description": "Bike insurance quotes",
  "published_version": null,
  "created_at": "..."
}
```

Use this `id` (here `1`) as `service_id` below.

**Negative test** — paste the same body again → **400**:

```json
{
  "name": ["service name already registered"]
}
```

---

## Step 3 — Upload the first spec version (v1.0.0)

`POST /api/services/{service_id}/specs/` (`service_id` = 1, authorized)

This is the kit's real `quote-api` v1 (`specs/quote-api/1-initial.yaml`), with the YAML embedded as a JSON string. **Paste the whole thing:**

```json
{
  "spec_text": "openapi: 3.0.3\ninfo:\n  title: Quote API\n  version: 1.0.0\n  description: 'Bike insurance quotes. Owner: Quotes team.'\npaths:\n  /quotes:\n    post:\n      operationId: createQuote\n      summary: Create a quote\n      requestBody:\n        required: true\n        content:\n          application/json:\n            schema:\n              $ref: '#/components/schemas/QuoteRequest'\n      responses:\n        '201':\n          description: Quote created\n          content:\n            application/json:\n              schema:\n                $ref: '#/components/schemas/Quote'\n        '400':\n          description: Invalid request\n  /quotes/{id}:\n    get:\n      operationId: getQuote\n      summary: Get a quote\n      parameters:\n      - name: id\n        in: path\n        required: true\n        schema:\n          type: string\n      responses:\n        '200':\n          description: The quote\n          content:\n            application/json:\n              schema:\n                $ref: '#/components/schemas/Quote'\n        '404':\n          description: Not found\n  /internal/pricing-cache:\n    delete:\n      operationId: clearPricingCache\n      summary: Clear the pricing cache (Quotes team only)\n      x-internal: true\n      responses:\n        '204':\n          description: Cache cleared\ncomponents:\n  schemas:\n    QuoteRequest:\n      type: object\n      required:\n      - vehicle\n      - rider\n      properties:\n        vehicle:\n          $ref: '#/components/schemas/Vehicle'\n        rider:\n          $ref: '#/components/schemas/Rider'\n    Vehicle:\n      type: object\n      required:\n      - make\n      - cc\n      properties:\n        make:\n          type: string\n        model:\n          type: string\n        cc:\n          type: integer\n    Rider:\n      type: object\n      required:\n      - age\n      properties:\n        age:\n          type: integer\n        city:\n          type: string\n    Quote:\n      type: object\n      required:\n      - quoteId\n      - status\n      - premium\n      properties:\n        quoteId:\n          type: string\n        status:\n          type: string\n          enum:\n          - DRAFT\n          - FINAL\n        premium:\n          $ref: '#/components/schemas/Premium'\n        createdAt:\n          type: string\n          format: date-time\n    Premium:\n      type: object\n      required:\n      - total\n      - currency\n      - breakdown\n      properties:\n        total:\n          type: number\n        currency:\n          type: string\n        breakdown:\n          type: array\n          items:\n            $ref: '#/components/schemas/BreakdownItem'\n    BreakdownItem:\n      type: object\n      required:\n      - label\n      - amount\n      properties:\n        label:\n          type: string\n        amount:\n          type: number\n"
}
```

Alternatively leave `spec_text` empty and choose a file in the `file` field (e.g. `specs/quote-api/1-initial.yaml` from the starter kit).

**Response 201:**

```json
{
  "id": 1,
  "service": 1,
  "version": "1.0.0",
  "status": "draft",
  "title": "Quote API",
  "openapi_version": "3.0.3",
  "created_at": "..."
}
```

The `version` is read from `info.version` — you never type it.

**Negative tests** (each → **400**):

```json
{ "spec_text": "not: a: spec" }
```

```json
{ "spec": ["invalid YAML/JSON: mapping values are not allowed here ..."] }
```

Missing `info.version`:

```json
{ "spec_text": "openapi: 3.0.3\ninfo:\n  title: X\npaths: {}\n" }
```

```json
{ "spec": ["missing info.version"] }
```

---

## Step 4 — Upload a second version (v1.1.0)

Same endpoint (`service_id` = 1, authorized). This compact v2 renames `premium.total` → `premium.amount` and drops the `/internal/pricing-cache` endpoint and the `premium.breakdown` field — perfect breaking-change material for the diff engine when it lands. **Paste:**

```json
{
  "spec_text": "openapi: 3.0.3\ninfo:\n  title: Quote API\n  version: 1.1.0\npaths:\n  /quotes:\n    post:\n      requestBody:\n        required: true\n        content:\n          application/json:\n            schema:\n              type: object\n              required: [vehicle, rider]\n              properties:\n                vehicle:\n                  type: object\n                  required: [make, cc]\n                  properties:\n                    make:\n                      type: string\n                    cc:\n                      type: integer\n                rider:\n                  type: object\n                  required: [age]\n                  properties:\n                    age:\n                      type: integer\n      responses:\n        '201':\n          description: Quote created\n          content:\n            application/json:\n              schema:\n                type: object\n                required: [quoteId, status, premium]\n                properties:\n                  quoteId:\n                    type: string\n                  status:\n                    type: string\n                  premium:\n                    type: object\n                    required: [amount, currency]\n                    properties:\n                      amount:\n                        type: number\n                      currency:\n                        type: string\n  /quotes/{id}:\n    get:\n      parameters:\n      - name: id\n        in: path\n        required: true\n        schema:\n          type: string\n      responses:\n        '200':\n          description: The quote\n          content:\n            application/json:\n              schema:\n                type: object\n                required: [quoteId, status, premium]\n                properties:\n                  quoteId:\n                    type: string\n                  status:\n                    type: string\n                  premium:\n                    type: object\n                    required: [amount, currency]\n                    properties:\n                      amount:\n                        type: number\n                      currency:\n                        type: string\n        '404':\n          description: Not found\n"
}
```

**Response 201:**

```json
{
  "id": 2,
  "service": 1,
  "version": "1.1.0",
  "status": "draft",
  "title": "Quote API",
  "openapi_version": "3.0.3",
  "created_at": "..."
}
```

(You can instead upload the kit's real `2-reorganised.yaml` via the `file` field — same result.)

---

## Step 5 — Browse what's registered

All GETs — no body, just **Execute**.

### 5a. List services

`GET /api/services/` — **Response 200:**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "quote-api",
      "owner_team": "Quotes team",
      "description": "Bike insurance quotes",
      "published_version": null,
      "created_at": "..."
    }
  ]
}
```

### 5b. Service detail

`GET /api/services/{service_id}/` (`1`) — same shape as one `results` item.

### 5c. List spec versions

`GET /api/services/{service_id}/specs/` (`1`) — **Response 200:**

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    { "id": 1, "service": 1, "version": "1.0.0", "status": "draft", "title": "Quote API", "openapi_version": "3.0.3", "created_at": "..." },
    { "id": 2, "service": 1, "version": "1.1.0", "status": "draft", "title": "Quote API", "openapi_version": "3.0.3", "created_at": "..." }
  ]
}
```

### 5d. Spec detail (raw + expanded contract)

`GET /api/services/{service_id}/specs/{spec_id}/` (`1`, spec `1`) — **Response 200** (trimmed):

```json
{
  "id": 1,
  "service": 1,
  "version": "1.0.0",
  "status": "draft",
  "title": "Quote API",
  "openapi_version": "3.0.3",
  "spec": "openapi: 3.0.3\ninfo:\n  title: Quote API\n...",
  "contract": {
    "paths": {
      "/quotes": {
        "post": {
          "requestBody": {
            "content": {
              "application/json": {
                "schema": {
                  "required": ["vehicle", "rider"],
                  "properties": {
                    "vehicle": { "type": "object", "required": ["make", "cc"], "properties": { "make": { "type": "string" }, "cc": { "type": "integer" } } }
                  }
                }
              }
            }
          }
        }
      }
    },
    "components": { "schemas": { "...": "..." } }
  }
}
```

Inside `contract` the requestBody schema is **fully resolved** — no `$ref` remains, `vehicle` is expanded inline. That's FR-02: comparisons will read these, so moving schemas around between files won't register as a change.

---

## Step 6 — Compare the two versions (breaking-change detection)

`POST /api/comparisons/` (authorized)

**Paste:**

```json
{
  "base_spec_id": 1,
  "target_spec_id": 2
}
```

(Use the spec ids from Step 5c's list — `base` = the old version, `target` = the new one. Both must belong to the same service; comparing specs of two different services returns **400**.)

**Response 201:**

```json
{
  "id": 4,
  "service": 1,
  "service_name": "quote-api",
  "base_spec": 1,
  "target_spec": 2,
  "base_version": "1.0.0",
  "target_version": "1.1.0",
  "summary": { "blocker": 1, "major": 0, "minor": 0, "info": 0 },
  "breaking": 1,
  "created_at": "..."
}
```

The system diffs the two stored contracts and records every change with a severity:

| Severity | Meaning | Breaking? |
| --- | --- | --- |
| `blocker` | endpoint/method removed, field removed, type changed, path parameter changed/renamed | yes |
| `major` | new required request field, response status removed | yes |
| `minor` | field added, field made optional, endpoint/method added | no |
| `info` | summary/description/deprecated/x-sunset metadata | no |

### 6b — Comparison detail with all changes

`GET /api/comparisons/{comparison_id}/` — no body. **Response 200** (this is a real example from Step 4's v1.0.0 → v1.1.0 pair):

```json
{
  "id": 4,
  "service": 1,
  "service_name": "quote-api",
  "base_spec": 1,
  "target_spec": 2,
  "base_version": "1.0.0",
  "target_version": "1.1.0",
  "summary": { "blocker": 1, "major": 0, "minor": 0, "info": 0 },
  "breaking": 1,
  "created_at": "...",
  "changes": [
    {
      "id": 12,
      "path": "/quotes/{id}",
      "method": "",
      "field_path": "",
      "side": "request",
      "change_type": "path_param_changed",
      "severity": "blocker",
      "breaking": true,
      "explanation": "path template /quotes/{id} changed to /quotes/{quoteId} (path parameter renamed)",
      "old_value": { "path": "/quotes/{id}" },
      "new_value": { "path": "/quotes/{quoteId}" },
      "location": "/quotes/{id}"
    }
  ]
}
```

Changes are ordered blockers → majors → minors → infos. `side` says which half of the contract changed: `request` (what consumers send), `response` (what consumers read), or `none` (endpoint-level/metadata).

### 6c — List all comparisons

`GET /api/comparisons/` — no body. Add `?service=1` to filter by service. **Response 200:** paginated list of the same comparison objects as in 6b (without `changes`).

Try a richer comparison: if you uploaded more versions, compare v1.1.0 → v2.0.0 (`{"base_spec_id": 2, "target_spec_id": 3}`) and you'll see `field_removed` blockers like `premium.breakdown[]amount`.

---

## Step 7 — Register a consumer (who calls this API, and which fields it uses)

`POST /api/consumers/` (authorized)

The body mirrors the starter kit's consumer files (`consumers/mobile-app.yaml`). **Paste:**

```json
{
  "consumer": "mobile-app",
  "team": "Mobile",
  "uses": [
    {
      "provider": "quote-api",
      "method": "POST",
      "path": "/quotes",
      "sends": ["vehicle.make", "vehicle.cc", "rider.age"],
      "reads": ["quoteId", "status", "premium.total", "premium.breakdown[].label", "premium.breakdown[].amount"]
    },
    {
      "provider": "quote-api",
      "method": "GET",
      "path": "/quotes/{id}",
      "sends": ["id"],
      "reads": ["quoteId", "status", "premium.total"]
    }
  ]
}
```

(`name` works as an alias for `consumer`; `sends`/`reads` are optional lists.)

**Response 201** — the stored declaration:

```json
{
  "id": 1,
  "name": "mobile-app",
  "team": "Mobile",
  "uses": [
    {
      "id": 1,
      "provider": "quote-api",
      "provider_id": 1,
      "method": "POST",
      "path": "/quotes",
      "sends": ["rider.age", "vehicle.cc", "vehicle.make"],
      "reads": ["premium.breakdown[].amount", "premium.breakdown[].label", "premium.total", "quoteId", "status"]
    }
  ]
}
```

Re-posting the same consumer name **replaces** its uses (idempotent re-registration).

**Negative test** — unknown provider → **400**:

```json
{ "consumer": "x", "team": "X", "uses": [{ "provider": "nope", "method": "POST", "path": "/p" }] }
```

```json
{ "uses": ["uses[0].provider: unknown service 'nope'"] }
```

### 7b — Browse consumers

- `GET /api/consumers/` — list (same shape as the 201 response, paginated)
- `GET /api/consumers/{consumer_id}/` — one consumer

---

## Step 8 — Publishing workflow (the gate)

`POST /api/publishing-attempts/` (authorized)

Try to publish a version. Contract Guard diffs it against the **latest earlier version** (published preferred), runs impact analysis against registered consumers, and decides:

- **no affected consumer** → auto-`approved`, version becomes `published`
- **any affected consumer** → `blocked`; the impact report is stored and a notification is sent

**Paste** (publish spec 1 — the first version, nothing to diff against → approved):

```json
{
  "spec_version_id": 1
}
```

**Response 201:**

```json
{
  "id": 4,
  "service": 1,
  "service_name": "quote-api",
  "spec_version": 1,
  "version": "1.0.0",
  "status": "approved",
  "comparison": null,
  "impact_report": null,
  "blocked_reasons": [],
  "affected_consumers": [],
  "decided_by": null,
  "decided_at": null,
  "comment": "",
  "created_at": "..."
}
```

**Now try spec 2** (the v1.1.0 from Step 4 that renamed `{id}` → `{quoteId}`, which `mobile-app` declared as `GET /quotes/{id}`):

```json
{
  "spec_version_id": 2
}
```

**Response 201 — blocked:**

```json
{
  "id": 5,
  "service": 1,
  "service_name": "quote-api",
  "spec_version": 2,
  "version": "1.1.0",
  "status": "blocked",
  "comparison": 5,
  "impact_report": 1,
  "blocked_reasons": [
    "declares GET — path template /quotes/{id} changed to /quotes/{quoteId} (path parameter renamed)"
  ],
  "affected_consumers": ["mobile-app"],
  "decided_by": null,
  "decided_at": null,
  "comment": "",
  "created_at": "..."
}
```

The version stays `draft`-with-`blocked`-attempt — the currently published version is untouched.

### 8b — Review: approve or reject a blocked attempt

`POST /api/publishing-attempts/{attempt_id}/approve/` (attempt 5 from above)

**Paste:**

```json
{ "comment": "Reviewed: path rename coordinated with mobile team" }
```

**Response 200:** attempt → `approved`, `decided_by`/`decided_at` filled, and the version is now the service's **published** one (check `GET /api/services/1/` → `published_version: "1.1.0"`).

`POST /api/publishing-attempts/{attempt_id}/reject/` instead keeps the version unpublished:

```json
{ "comment": "mobile-app still reads premium.breakdown[].amount; coordinate first" }
```

Both endpoints return **400** if the attempt isn't blocked (already decided) — state machine enforced.

### 8c — Attempt history

`GET /api/publishing-attempts/` — no body. Every attempt ever made, newest first, with outcomes (FR-08).

---

## Step 9 — Notifications & the built-in webhook receiver (FR-10)

Every attempt and decision fires a notification. By default Contract Guard posts to **its own built-in receiver** — no second server needed:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/webhook-events/receive/` | records any JSON payload (no auth, like an external receiver) |
| `GET /api/webhook-events/` | newest 100 received events |
| `DELETE /api/webhook-events/` | clear them |

**Response of the GET** (after the Step 8 cycle):

```json
[
  {
    "id": 5,
    "received_at": "...",
    "path": "/api/webhook-events/receive/",
    "body": {
      "event": "publish.rejected",
      "service": "quote-api",
      "version": "2.0.0",
      "attempt_id": 6,
      "status": "rejected",
      "blocked_reasons": ["declares GET /quotes/{id} (reads premium.breakdown[].amount) — field 'premium.breakdown[].amount' was removed from response 200 of GET /quotes/{id}"],
      "affected_consumers": ["mobile-app"]
    }
  }
]
```

Notification delivery is also recorded per attempt in the DB (`delivered` + HTTP status); a down receiver never fails a publishing operation.

*(Optional external receiver: start the kit's receiver with `docker compose up` in `sde-startup-kit/contract-guard-starter-kit/` and restart the server with `WEBHOOK_RECEIVER_URL=http://localhost:9900/contract-guard python manage.py runserver` — notifications then go there instead, viewed at http://localhost:9900.)*

---

## Cheat sheet

| Step | Endpoint | Body to paste |
| --- | --- | --- |
| Register | `POST /api/auth/register/` | `{username, password, email?}` |
| Log in | `POST /api/auth/login/` | `{username, password}` |
| Register service | `POST /api/services/` | `{name, owner_team, description?}` |
| Upload spec | `POST /api/services/{id}/specs/` | `{spec_text: "..."}` **or** `file` |
| List services | `GET /api/services/` | — |
| Service detail | `GET /api/services/{id}/` | — |
| List versions | `GET /api/services/{id}/specs/` | — |
| Version detail | `GET /api/services/{id}/specs/{spec_id}/` | — |
| Compare versions | `POST /api/comparisons/` | `{base_spec_id, target_spec_id}` |
| Comparison list | `GET /api/comparisons/` (`?service={id}`) | — |
| Comparison detail | `GET /api/comparisons/{id}/` | — |
| Register consumer | `POST /api/consumers/` | `{consumer, team, uses: [{provider, method, path, sends?, reads?}]}` |
| Consumer list/detail | `GET /api/consumers/`, `GET /api/consumers/{id}/` | — |
| Publish attempt | `POST /api/publishing-attempts/` | `{spec_version_id}` |
| Attempt history | `GET /api/publishing-attempts/` | — |
| Approve attempt | `POST /api/publishing-attempts/{id}/approve/` | `{comment?}` |
| Reject attempt | `POST /api/publishing-attempts/{id}/reject/` | `{comment?}` |
| Webhook receiver | `POST /api/webhook-events/receive/` | any JSON payload |
| Receiver events | `GET /api/webhook-events/`, `DELETE` clears | — |

All FRs (FR-01 … FR-10) are now implemented except FR-06's public endpoint (`GET /api/comparisons/{id}/impact/` — impact currently runs inside the publishing gate; say the word and it gets its own endpoint) and the FR-09 dashboard UI.

# UIWorkflow.md — How Contract Guard is meant to be used, screen by screen

This is the intended day-to-day workflow of the React UI, told as one worked example:
**a provider team ships a new version of `quote-api` without breaking `mobile-app`.**

Follow the numbered steps in order on a fresh database and you'll exercise every feature.

---

## 0. The app at a glance

| Page | Route | What it's for |
| --- | --- | --- |
| Dashboard | `/` | Landing page: counts, recent comparisons, blocked publishes waiting for review |
| Services | `/services` | The registry of provider APIs |
| Service detail | `/services/{id}` | One service: its spec versions, upload, compare, publish |
| Comparisons | `/comparisons` | Every diff ever run |
| Comparison detail | `/comparisons/{id}` | The changes of one diff, worst first |
| Consumers | `/consumers` | Who calls which API, and which fields they depend on |
| Publishing | `/publishing` | The gate: every attempt + approve/reject decisions |
| Notifications | `/notifications` | What the webhook receiver got (an external system would get the same) |
| Log in / Register | `/login`, `/register` | JWT account; token attached to every request automatically |

**Two roles use the same app:**

- the **provider team** (owns `quote-api`) — registers the service, uploads spec versions, publishes;
- the **consumer team** (owns `mobile-app`) — registers what their app calls and which fields it reads.

**Running it:** Django API on `:8765`, React app on `:5173` (Vite proxies `/api`). Open **http://localhost:5173**.
Swagger for the raw API is linked in the page footer.

---

## 1. Create an account

First visit → you're redirected to **Log in**. Click **Create an account**.

- Fill **Username** (min 3 chars), **Password** (min 8), Email optional → **Register**.
- You land on the **Dashboard**, greeted by name in the top bar.

The Dashboard is empty on day one — the stat cards show zeros and the empty-state text
tells you what to do first: *"register a service, upload two spec versions, then compare them."*

*(Already have an account? Just log in. A wrong password shows "Invalid username or password".)*

---

## 2. Register the service (provider team)

**Services → Register service** and fill the dialog:

| Field | Value |
| --- | --- |
| Service name | `quote-api` |
| Owner team | `Quotes team` |
| Description | `Bike insurance quotes` |

Registering drops you straight into the new service's detail page. The chip says
**"nothing published yet"** and the version list is empty with a hint to upload v1.

*(Registering the same name twice → 400 shown in the dialog: `name: service name already registered`.)*

---

## 3. Upload spec versions

On the service page, **Upload spec**. Two ways — both always available:

- **Paste text** tab: paste OpenAPI 3.0 YAML/JSON into the mono-spaced editor;
- **Upload file** tab: pick a `.yaml` / `.yml` / `.json` file (max 2 MB).

You never type the version number — it's read from `info.version` and shown in the table.

Upload **v1.0.0** (the current live API), then later **v1.1.0** (the proposal: renames the path
parameter `{id}` → `{quoteId}` and reorganizes the schema files). The versions table now shows:

| Version | Status | Title | Uploaded | Actions |
| --- | --- | --- | --- | --- |
| v1.1.0 | draft | Quote API | just now | View · Publish |
| v1.0.0 | draft | Quote API | 2 min ago | View · Publish |

**View** opens the spec read-only, with two tabs:
- **Raw spec** — exactly what was uploaded;
- **Resolved contract** — every `$ref` expanded; this is what the differ actually reads,
  so re-organizing schema files between versions is invisible (a good thing).

Every upload lands as **draft**. Only the publishing gate (step 7) can make something *published*.

*(Garbage input is rejected in the dialog with a readable message: invalid YAML, not OpenAPI 3.0.x, missing `info.version`, broken `$ref` — a spec that fails upload can never poison the registry.)*

---

## 4. See what changed between the two versions

**Compare versions** on the service page → pick

- **Base version (old):** `v1.0.0 (#1)`
- **Target version (new):** `v1.1.0 (#2)`

(both dropdowns list this service's versions; comparing across services is refused).

You land on the **comparison detail** page. For our pair:

```
quote-api: v1.0.0 → v1.1.0        [1 blocker]  [breaking]
```

and the changes table, **worst first**:

| Severity | Change | Location | Side | Explanation |
| --- | --- | --- | --- | --- |
| blocker | path_param_changed | `/quotes/{id}` | request | path template /quotes/{id} changed to /quotes/{quoteId} (path parameter renamed) |

Reading it: **severity** = how bad, **side** = who feels it (`request` = what callers send,
`response` = what callers read, `none` = endpoint-level), **explanation** = plain English.
The chips at the top (`blocker / major / minor / info`) are the same vocabulary used everywhere else.

Note the rename shows as **one** blocker — `{id}` and `{quoteId}` are recognized as the same
endpoint shape, not "endpoint removed + endpoint added". Upload more versions (e.g. the kit's
v2.0.0) and richer diffs appear: `field_removed` blockers like `premium.breakdown[].amount`,
deprecation INFO rows, added minors.

The **Comparisons** page lists every diff ever run (filterable view, one row per pair) —
this is the service's breaking-change history (FR-08).

---

## 5. Register the consumers (consumer team)

Impact analysis only knows what it's told. On **Consumers → Register consumer**, declare
`mobile-app`: name + team, then one row per endpoint it calls ("uses"):

| Provider | Method | Path | Sends | Reads |
| --- | --- | --- | --- | --- |
| quote-api | POST | `/quotes` | `vehicle.make, vehicle.cc, rider.age` | `quoteId, status, premium.total, premium.breakdown[].amount` |
| quote-api | GET | `/quotes/{id}` | `id` | `quoteId, status, premium.total` |

- Providers are picked from the services actually registered — an unknown one is a form error.
- Field paths use **dots for nesting, `[]` for array items** (`premium.breakdown[].amount`) —
  the same notation the comparison page shows, so the two match up by eye and by code.
- **Add use** adds another row; the trash icon removes one.
- Re-posting the same consumer name **replaces** its uses — fixing a stale declaration is
  just re-registering it, no delete needed.

The consumer card now shows each use with its method chip, the provider+path, and its
sends/reads lists. This declaration is the entire input for the publish gate.

---

## 6. Publish the safe version (auto-approved)

Back on the service page, press **Publish** on **v1.0.0**.

Result dialog: **approved** — there's no earlier version to diff against, so nothing can
break. The service header chip flips to **"published: v1.0.0"**.

This is the rule in action: *no affected consumer ⇒ publishes immediately* (FR-07).

---

## 7. Publish the risky version (the gate blocks it)

Press **Publish** on **v1.1.0**. Now the gate has work to do: it diffs v1.1.0 against the
published v1.0.0, matches every breaking change against the consumers' declarations, and
finds `mobile-app` still calls `GET /quotes/{id}`.

Result dialog: **blocked**

- **Affected consumers:** `mobile-app`
- **Reasons:** *"declares GET — path template /quotes/{id} changed to /quotes/{quoteId} (path parameter renamed)"*
- The version stays **draft**; the published v1.0.0 is untouched.
- **Go to publishing** takes you straight to the review queue.

Nothing was auto-published; a human must now decide.

---

## 8. Review the blocked attempt

**Publishing** lists every attempt ever made — status, reasons, affected consumers,
who decided and when. Blocked rows show two buttons:

**Approve** → dialog warns *"Approving publishes this version even though 1 consumer(s)
are affected."* Add a comment (e.g. *"Reviewed: path rename coordinated with mobile team,
they ship v1.1.0 the same day"*) → **Approve & publish**.

→ Banner: *"Attempt #5 approved — v1.1.0 is now published."*
The service page chip becomes **published: v1.1.0**, and v1.0.0 is demoted to draft —
one published version per service, always.

**Reject** (instead) → comment *"mobile-app still reads premium.breakdown[].amount;
coordinate first"* → Banner: *"Attempt #N rejected — vX stays unpublished."*
The version returns to draft; the published version never changed. This is what you'd do to
a hypothetical v2.0.0 that removes fields mobile-app still reads. Re-uploading a fixed spec
and attempting again is the normal next move.

Both actions are recorded on the attempt row (decided_by / decided_at / comment) —
this page is the audit log (FR-08).

---

## 9. Watch the notifications

**Notifications** shows what the built-in webhook receiver captured. After the cycle above:

- `publish.approved` — quote-api v1.0.0
- `publish.blocked` — quote-api v1.1.0, affected: mobile-app, with the reasons
- `publish.approved` — quote-api v1.1.0 (after the human approval)

Each card renders the event chip, affected consumers, and the **exact JSON payload**
an external receiver (chat bot, email gateway) would have received. Delivery of every
notification is also recorded per attempt in the backend, so a down receiver never
fails a publishing operation. **Clear** empties the log.

---

## 10. The quiet version (no drama)

Later, upload **v2.1.0** — it only *adds* optional fields (`premium.taxes`, `rider.ncbPercent`).

- **Compare versions** shows 3 minors, non-breaking.
- **Publish** → result dialog: **approved** instantly. No consumer depends on fields that
  don't exist yet, so there's nothing to review.

That's the intended rhythm: additive versions flow through, breaking ones stop for a human.

---

## 11. Steady state — the loop teams settle into

```
provider uploads new version (draft)
        │
        ▼
compare against published  ──►  comparison page (history)
        │
        ▼
publish attempt
        │
   ┌────┴─────────┐
   no affected     affected consumer
   consumer        │
   │               ▼
   ▼           BLOCKED ──► publishing queue ──► approve (publish) / reject (back to draft)
approved           ▲                                  │
   │               └──── fix the spec, re-upload ────┘
   ▼
version becomes the one published
        │
        ▼
notification fired to the receiver (built-in or external)
```

- The **Dashboard** is the daily landing page: breaking-change count, blocked attempts
  waiting for review, published X/Y — click through to any of them.
- Consumers re-register when their usage changes; the registry stays honest because
  re-posting is idempotent.
- Everything is retained: comparisons, per-change rows, impact reports, attempts,
  decisions with comments, notifications. The history pages are the audit trail.

---

## Status cheat sheet

| Thing | Values | Meaning |
| --- | --- | --- |
| Spec version | `draft` | uploaded, not live |
| | `published` | the service's single live version |
| | `blocked` | a publish attempt was blocked (still effectively draft) |
| Publishing attempt | `approved` | published (auto or by a reviewer) |
| | `blocked` | waiting for review |
| | `rejected` | reviewer said no; version stays unpublished |
| Change severity | `blocker` / `major` | breaking — triggers the gate |
| | `minor` / `info` | safe — never blocks |

## Good to know

- **401 anywhere** → the app drops the stale token and returns you to Log in
  (access tokens live 8h; log in again to refresh).
- **Compare is per-service** — the dropdowns only offer that service's versions.
- **First version publishes free** — there's nothing to break yet.
- **Rejected ≠ lost** — fix the spec, upload a new version, attempt again; the old
  attempt stays in the history for the audit trail.

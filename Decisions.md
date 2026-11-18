# Decisions.md — Version Comparison Rules

How Contract Guard decides what changed between two spec versions, and how bad each change is.
One page, plain language. Everything here is implemented in `backend/base/services/differ.py`.

---

## 1. What gets compared

- Two uploaded specs: **base** (old) and **target** (new).
- Both are compared *after* `$ref` expansion (references resolved at upload time).
- Only OpenAPI 3.0.x specs are ever in the registry, so both sides have the same shape.

---

## 2. How endpoints are matched

Endpoints are matched by **path shape**, not exact text:

| Base | Target | Same endpoint? |
| --- | --- | --- |
| `/quotes/{id}` | `/quotes/{id}` | yes |
| `/quotes/{id}` | `/quotes/{quoteId}` | **yes** — both normalize to `/quotes/{}` |
| `/quotes` | `/quotes/{id}` | no (different shape) |

- `{anything}` in a path counts as the same placeholder.
- So renaming a path variable is reported **once** as a blocker (`path_param_changed`), not as "endpoint removed + endpoint added".

---

## 3. The severity ladder

| Severity | Meaning | Breaking? | Publish gate effect |
| --- | --- | --- | --- |
| **BLOCKER** | A consumer will break at runtime | yes | publish attempt gets **blocked** if a consumer is affected |
| **MAJOR** | A consumer *might* break (new required input, lost response) | yes | same as blocker |
| **MINOR** | Backwards-compatible addition/relaxation | no | publish goes through |
| **INFO** | Documentation / deprecation marks only | no | publish goes through |

**Rule of thumb:** BLOCKER/MAJOR = "something that used to work may stop working".
MINOR/INFO = "additive or cosmetic".

---

## 4. The rules

### BLOCKER — things that break consumers today

| # | What changed | Change type |
| --- | --- | --- |
| B1 | An endpoint (path) is gone | `endpoint_removed` |
| B2 | A method (GET/POST/…) is gone from an endpoint | `method_removed` |
| B3 | A field disappeared (or was renamed — same thing to the differ) | `field_removed` |
| B4 | A field's type changed (e.g. string → integer) | `field_type_changed` |
| B5 | A path parameter was renamed / added / removed, or its type changed | `path_param_changed` |

### MAJOR — likely breakage

| # | What changed | Change type |
| --- | --- | --- |
| M1 | An existing request field is now **required** (consumers must start sending it) | `required_added` (request side) |
| M2 | A response status code disappeared (e.g. `200` removed) | `response_removed` |
| M3 | A **new field appeared in the request body and is required** | `field_added` (request side, required) |

### MINOR — safe, backwards-compatible

| # | What changed | Change type |
| --- | --- | --- |
| N1 | A new optional field appeared (request or response) | `field_added` |
| N2 | A new required field appeared **in a response** (consumers just ignore what they don't read) | `field_added` (response side) |
| N3 | A request field is no longer required (easier on consumers) | `required_removed` |
| N4 | A new endpoint appeared | `path_added` |
| N5 | A new method appeared on an existing endpoint | `method_added` |

### INFO — documentation & deprecation

| # | What changed | Change type |
| --- | --- | --- |
| I1 | `summary` / `description` of an operation or the API changed | `metadata_changed` |
| I2 | An operation or field is now marked `deprecated: true` (or un-marked) | `metadata_changed` |
| I3 | An `x-sunset` date was added/changed (our "this will die on …" marker) | `metadata_changed` |

---

## 5. Field paths

Nested fields use dots; array items use `[]`:

```
premium.total                    → the "total" field inside "premium"
premium.breakdown[].amount      → "amount" inside each item of the "breakdown" array
rider.ncbPercent                → nested request field
```

These match exactly how consumer files declare `sends:` / `reads:`, which is what makes
impact analysis a simple string comparison.

---

## 6. Worked examples (from the starter kit)

| Version pair | What changed | Result |
| --- | --- | --- |
| quote-api 1.0 → 1.1 | `/quotes/{id}` → `/quotes/{quoteId}` | 1 **blocker** (`path_param_changed`) |
| quote-api 1.1 → 2.0 | `premium.breakdown[].amount` removed, `value` added | **2 blockers** (`field_removed`) + 2 minors |
| quote-api 2.0 → 2.1 | `premium.taxes`, `rider.ncbPercent` added | 3 minors, non-breaking |
| policy-api 1.1 → 2.0 | fields marked deprecated in 1.1 are now removed | 4 **blockers**; the deprecations themselves were INFO in the previous step |
| claims-api v2 (bad `$ref`) | spec doesn't even parse | rejected **at upload**, never compared |

---

## 7. What we deliberately do NOT check

Kept out of scope on purpose (static MVP, per Plan.md):

- **Enum / format narrowing** — removing an enum value or tightening `format` is not flagged.
- **allOf / oneOf / anyOf composition** — compared as-is, not decomposed.
- **Content types** — only `application/json` bodies and responses are inspected.
- **Query / header parameters** — only path parameters are checked.
- **Default values, min/max, patterns** — constraint changes are ignored.
- **Runtime behaviour** — we never call the real service; everything is derived from the uploaded text.

---

## 8. How the gate uses these rules

1. Diff produces a list of changes, each with a severity.
2. `breaking = true` for every BLOCKER and MAJOR.
3. Impact analysis joins each **breaking** change against consumer declarations
   (same service + same normalized path + method; field changes must touch a field the
   consumer `sends` (request) or `reads` (response)).
4. ≥1 affected consumer → publish attempt is **blocked**; else auto-**approved**.

Changes are always displayed **blockers first**, then majors, minors, info.

---

## 9. Comparison in one sentence

> Two versions are compatible for a given consumer if nothing the consumer
> sends was made harder to send, and nothing the consumer reads was removed
> or changed shape.

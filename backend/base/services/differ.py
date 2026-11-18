"""Contract comparison (FR-03) and change classification (FR-04).

Compares two $ref-expanded contracts (as stored on SpecVersion.contract)
and returns a list of change dicts. Classification follows the Plan.md
catalog:

  BLOCKER  endpoint/method removed, field removed, field type changed,
           path parameter changed
  MAJOR    field made required (request side), response status removed,
           new required request field
  MINOR    optional field added, field made optional, endpoint/method
           added, new response-side required field
  INFO     description/summary/deprecated metadata changes

Known MVP limitations (deliberate, per Plan.md):
  - enum/format narrowing and allOf/oneOf composition are not compared
  - only `application/json` request/response bodies are inspected
  - query/header parameters other than path parameters are ignored

Field paths use the kit convention: dots for nesting, [] for array items,
e.g. premium.breakdown[].amount.
"""
import re

from base.models import ChangeSeverity, ChangeSide, ChangeType

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
MAX_DEPTH = 64

BREAKING_SEVERITIES = {ChangeSeverity.BLOCKER, ChangeSeverity.MAJOR}

SEVERITY_ORDER = {
    ChangeSeverity.BLOCKER: 0,
    ChangeSeverity.MAJOR: 1,
    ChangeSeverity.MINOR: 2,
    ChangeSeverity.INFO: 3,
}


def normalize_path(path):
    """'/quotes/{id}' and '/quotes/{quoteId}' both -> '/quotes/{}'.

    Path-template identity is about shape, not parameter names; renames
    are reported separately as PATH_PARAM_CHANGED.
    """
    return re.sub(r"\{[^}]+\}", "{}", path)


def _change(path, method, field_path, side, change_type, severity, explanation, old=None, new=None):
    return {
        "path": path,
        "method": method,
        "field_path": field_path,
        "side": side,
        "change_type": change_type,
        "severity": severity,
        "breaking": severity in BREAKING_SEVERITIES,
        "explanation": explanation,
        "old_value": old,
        "new_value": new,
    }


def _join(segs):
    """['premium', 'breakdown', '[]', 'amount'] -> 'premium.breakdown[].amount'."""
    out = ""
    for s in segs:
        if s == "[]":
            out += "[]"
        else:
            out += s if not out else (("." if not out.endswith("[]") else "") + s)
    return out


def _is_object_schema(s):
    return isinstance(s, dict) and (s.get("type") == "object" or isinstance(s.get("properties"), dict))


def _is_array_schema(s):
    return isinstance(s, dict) and s.get("type") == "array"


def _body_schema(operation):
    try:
        return operation["requestBody"]["content"]["application/json"]["schema"]
    except (KeyError, TypeError):
        return None


def _resp_schema(response):
    try:
        return response["content"]["application/json"]["schema"]
    except (KeyError, TypeError):
        return None


def _diff_object(old, new, segs, side, ctx, changes, depth):
    """Both schemas are objects: compare required lists and properties."""
    r_old = list(old.get("required") or [])
    r_new = list(new.get("required") or [])
    props_old = old.get("properties") or {}
    props_new = new.get("properties") or {}
    # required-changes are only meaningful for fields present in both versions;
    # added/removed fields are reported by the field_added/field_removed rules
    common = set(props_old) & set(props_new)

    for f in r_new:
        if f not in r_old and f in common:
            sev = ChangeSeverity.MAJOR if side == ChangeSide.REQUEST else ChangeSeverity.MINOR
            changes.append(_change(
                "", "", _join(segs + [f]), side, ChangeType.REQUIRED_ADDED, sev,
                f"field '{_join(segs + [f])}' is now required in {ctx}",
                old={"required": r_old}, new={"required": r_new},
            ))
    for f in r_old:
        if f not in r_new and f in common:
            changes.append(_change(
                "", "", _join(segs + [f]), side, ChangeType.REQUIRED_REMOVED, ChangeSeverity.MINOR,
                f"field '{_join(segs + [f])}' is no longer required in {ctx}",
                old={"required": r_old}, new={"required": r_new},
            ))

    for f, schema_old in props_old.items():
        label = _join(segs + [f])
        if f not in props_new:
            changes.append(_change(
                "", "", label, side, ChangeType.FIELD_REMOVED, ChangeSeverity.BLOCKER,
                f"field '{label}' was removed from {ctx}",
                old=schema_old, new=None,
            ))
        else:
            _diff_schema(schema_old, props_new[f], segs + [f], side, ctx, changes, depth + 1)

    for f, schema_new in props_new.items():
        if f in props_old:
            continue
        label = _join(segs + [f])
        sev = ChangeSeverity.MAJOR if (side == ChangeSide.REQUEST and f in r_new) else ChangeSeverity.MINOR
        changes.append(_change(
            "", "", label, side, ChangeType.FIELD_ADDED, sev,
            f"field '{label}' was added to {ctx}"
            + (" and is required" if sev == ChangeSeverity.MAJOR else ""),
            old=None, new=schema_new,
        ))

    # deprecation markers on fields that exist in both versions (INFO)
    for f in sorted(common):
        old_p, new_p = props_old[f] or {}, props_new[f] or {}
        if not isinstance(old_p, dict) or not isinstance(new_p, dict):
            continue
        label = _join(segs + [f])
        if not old_p.get("deprecated") and new_p.get("deprecated"):
            changes.append(_change(
                "", "", label, side, ChangeType.METADATA_CHANGED, ChangeSeverity.INFO,
                f"field '{label}' is now marked deprecated in {ctx}",
                old={"deprecated": False}, new={"deprecated": True},
            ))
        if old_p.get("x-sunset") != new_p.get("x-sunset") and new_p.get("x-sunset"):
            changes.append(_change(
                "", "", label, side, ChangeType.METADATA_CHANGED, ChangeSeverity.INFO,
                f"field '{label}' has x-sunset {new_p.get('x-sunset')!r} in {ctx}",
                old=old_p.get("x-sunset"), new=new_p.get("x-sunset"),
            ))


def _diff_schema(old, new, segs, side, ctx, changes, depth=0):
    if depth > MAX_DEPTH:
        return
    if _is_object_schema(old) and _is_object_schema(new):
        _diff_object(old, new, segs, side, ctx, changes, depth)
    elif _is_array_schema(old) and _is_array_schema(new):
        _diff_schema(old.get("items") or {}, new.get("items") or {}, segs + ["[]"], side, ctx, changes, depth + 1)
    else:
        t_old = old.get("type") if isinstance(old, dict) else None
        t_new = new.get("type") if isinstance(new, dict) else None
        if t_old != t_new:
            label = _join(segs) or "(body)"
            changes.append(_change(
                "", "", _join(segs), side, ChangeType.FIELD_TYPE_CHANGED, ChangeSeverity.BLOCKER,
                f"field '{label}' type changed from {t_old or 'untyped'} to {t_new or 'untyped'} in {ctx}",
                old={"type": t_old}, new={"type": t_new},
            ))


def _path_params(op):
    """Path parameters in declaration order."""
    return [
        p for p in (op.get("parameters") or [])
        if isinstance(p, dict) and p.get("in") == "path" and p.get("name")
    ]


def _diff_operation(path, method, old_op, new_op, changes, renamed=False):
    label = f"{method.upper()} {path}"

    # path parameters: on rename, params are paired by position and the
    # rename is reported once at contract level (see compare_contracts)
    if not renamed:
        def params_by_name(op):
            return {p["name"]: p for p in _path_params(op)}

        pp_old, pp_new = params_by_name(old_op), params_by_name(new_op)
        for name, p in pp_old.items():
            if name not in pp_new:
                changes.append(_change(
                    path, method, name, ChangeSide.REQUEST, ChangeType.PATH_PARAM_CHANGED, ChangeSeverity.BLOCKER,
                    f"path parameter '{name}' was removed from {label}",
                    old={"name": name, "schema": p.get("schema")}, new=None,
                ))
            else:
                t_old = (p.get("schema") or {}).get("type")
                t_new = (pp_new[name].get("schema") or {}).get("type")
                if t_old != t_new:
                    changes.append(_change(
                        path, method, name, ChangeSide.REQUEST, ChangeType.PATH_PARAM_CHANGED, ChangeSeverity.BLOCKER,
                        f"path parameter '{name}' type changed from {t_old or 'untyped'} to {t_new or 'untyped'} in {label}",
                        old={"type": t_old}, new={"type": t_new},
                    ))
        for name, p in pp_new.items():
            if name not in pp_old:
                changes.append(_change(
                    path, method, name, ChangeSide.REQUEST, ChangeType.PATH_PARAM_CHANGED, ChangeSeverity.BLOCKER,
                    f"new path parameter '{name}' added to {label}",
                    old=None, new={"name": name, "schema": p.get("schema")},
                ))

    # metadata (INFO)
    for field in ("summary", "description"):
        if old_op.get(field) != new_op.get(field):
            changes.append(_change(
                path, method, field, ChangeSide.NONE, ChangeType.METADATA_CHANGED, ChangeSeverity.INFO,
                f"{field} of {label} changed",
                old=old_op.get(field), new=new_op.get(field),
            ))
    if bool(old_op.get("deprecated")) != bool(new_op.get("deprecated")):
        dep = bool(new_op.get("deprecated"))
        changes.append(_change(
            path, method, "deprecated", ChangeSide.NONE, ChangeType.METADATA_CHANGED, ChangeSeverity.INFO,
            f"{label} is {'now marked deprecated' if dep else 'no longer marked deprecated'}",
            old=old_op.get("deprecated"), new=new_op.get("deprecated"),
        ))
    if old_op.get("x-sunset") != new_op.get("x-sunset") and new_op.get("x-sunset"):
        changes.append(_change(
            path, method, "x-sunset", ChangeSide.NONE, ChangeType.METADATA_CHANGED, ChangeSeverity.INFO,
            f"{label} has x-sunset {new_op.get('x-sunset')!r}",
            old=old_op.get("x-sunset"), new=new_op.get("x-sunset"),
        ))

    # request body
    old_body, new_body = _body_schema(old_op), _body_schema(new_op)
    if old_body is not None and new_body is not None:
        _diff_schema(old_body, new_body, [], ChangeSide.REQUEST, f"request body of {label}", changes)

    # responses
    old_resps = old_op.get("responses") or {}
    new_resps = new_op.get("responses") or {}
    for code in old_resps:
        if code not in new_resps:
            changes.append(_change(
                path, method, "", ChangeSide.RESPONSE, ChangeType.RESPONSE_REMOVED, ChangeSeverity.MAJOR,
                f"response {code} was removed from {label}",
                old={code: old_resps[code]}, new=None,
            ))
            continue
        old_schema, new_schema = _resp_schema(old_resps[code]), _resp_schema(new_resps[code])
        if old_schema is not None and new_schema is not None:
            _diff_schema(old_schema, new_schema, [], ChangeSide.RESPONSE, f"response {code} of {label}", changes)


def compare_contracts(base, target):
    """Diff two $ref-expanded contracts -> list of change dicts (FR-03, FR-04).

    Endpoints are matched by normalized path template (placeholder shape),
    so renaming a path parameter is a PATH_PARAM_CHANGED blocker, not an
    endpoint removal plus an endpoint addition.
    """
    changes = []

    def path_map(paths):
        """normalized path -> {real, ops} (first real path wins per shape)."""
        out = {}
        for path, ops in (paths or {}).items():
            norm = normalize_path(path)
            if norm in out:
                continue
            out[norm] = {"real": path, "ops": ops}
        return out

    base_map, target_map = path_map(base.get("paths")), path_map(target.get("paths"))

    for norm, b in base_map.items():
        if norm not in target_map:
            methods = [m.upper() for m in b["ops"] if m in HTTP_METHODS]
            changes.append(_change(
                b["real"], "", "", ChangeSide.NONE, ChangeType.ENDPOINT_REMOVED, ChangeSeverity.BLOCKER,
                f"endpoint {b['real']} ({', '.join(methods) or 'no methods'}) was removed",
                old={"methods": methods}, new=None,
            ))
            continue

        t = target_map[norm]
        renamed = b["real"] != t["real"]
        if renamed:
            changes.append(_change(
                b["real"], "", "", ChangeSide.REQUEST, ChangeType.PATH_PARAM_CHANGED, ChangeSeverity.BLOCKER,
                f"path template {b['real']} changed to {t['real']} (path parameter renamed)",
                old={"path": b["real"]}, new={"path": t["real"]},
            ))

        b_ops = {m: op for m, op in b["ops"].items() if m in HTTP_METHODS and isinstance(op, dict)}
        t_ops = {m: op for m, op in t["ops"].items() if m in HTTP_METHODS and isinstance(op, dict)}
        for m, b_op in b_ops.items():
            if m not in t_ops:
                changes.append(_change(
                    b["real"], m, "", ChangeSide.NONE, ChangeType.METHOD_REMOVED, ChangeSeverity.BLOCKER,
                    f"method {m.upper()} was removed from endpoint {b['real']}",
                    old=None, new=None,
                ))
            else:
                _diff_operation(b["real"], m, b_op, t_ops[m], changes, renamed=renamed)
        for m, t_op in t_ops.items():
            if m not in b_ops:
                changes.append(_change(
                    b["real"], m, "", ChangeSide.NONE, ChangeType.METHOD_ADDED, ChangeSeverity.MINOR,
                    f"method {m.upper()} was added to endpoint {b['real']}",
                    old=None, new=None,
                ))

    for norm, t in target_map.items():
        if norm not in base_map:
            changes.append(_change(
                t["real"], "", "", ChangeSide.NONE, ChangeType.PATH_ADDED, ChangeSeverity.MINOR,
                f"endpoint {t['real']} was added",
                old=None, new=None,
            ))

    base_info, target_info = base.get("info") or {}, target.get("info") or {}
    for field in ("title", "description"):
        if base_info.get(field) != target_info.get(field):
            changes.append(_change(
                "", "", f"info.{field}", ChangeSide.NONE, ChangeType.METADATA_CHANGED, ChangeSeverity.INFO,
                f"info.{field} changed",
                old=base_info.get(field), new=target_info.get(field),
            ))

    return changes


def sort_changes(changes):
    """Blockers first, then majors, minors, info; stable within severity."""
    return sorted(changes, key=lambda c: (SEVERITY_ORDER[c["severity"]], c["path"], c["field_path"]))

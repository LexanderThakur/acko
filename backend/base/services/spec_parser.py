"""OpenAPI specification parsing and validation (FR-01, FR-02).

Turns raw YAML/JSON text into:
  - `info` (title, version) extracted for registry metadata
  - a $ref-expanded `contract` stored on SpecVersion, so comparisons work
    on the real contract rather than file layout

Only local references (`#/components/...`) are supported, which is what
the kit's specs use.
"""
import json

import yaml

MAX_SPEC_BYTES = 2 * 1024 * 1024  # 2 MB guard against accidental huge uploads


class SpecParseError(Exception):
    """Raised when an uploaded spec cannot be parsed or is not valid OpenAPI."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _load_spec(text):
    """Parse raw text as YAML (which also covers JSON) into a dict."""
    if len(text) > MAX_SPEC_BYTES:
        raise SpecParseError("spec is too large (max 2 MB)")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SpecParseError(f"invalid YAML/JSON: {e}") from e
    if not isinstance(data, dict):
        raise SpecParseError("spec must be a YAML/JSON mapping (object)")
    return data


def _check_openapi(data):
    version = str(data.get("openapi", ""))
    if not version:
        raise SpecParseError("missing openapi version field")
    if not version.startswith("3.0."):
        raise SpecParseError(f"only OpenAPI 3.0.x is supported, got '{version}'")
    info = data.get("info")
    if not isinstance(info, dict) or not info.get("version"):
        raise SpecParseError("missing info.version")


def _expand_refs(node, root, depth=0):
    """Recursively replace local $refs with the pointed-to schema object.

    Mutates and returns `node`. Bounded depth guards against circular refs.
    """
    if depth > 32:
        raise SpecParseError("spec has too-deeply nested $refs (possible circular reference)")
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            target = root
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(target, dict) or part not in target:
                    raise SpecParseError(f"broken $ref: '{ref}'")
                target = target[part]
            merged = _expand_refs(target, root, depth + 1)
            # keep sibling keys (e.g. description next to $ref), $ref resolved wins
            merged = {**merged, **{k: v for k, v in node.items() if k != "$ref"}}
            return merged
        return {k: _expand_refs(v, root, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_refs(v, root, depth + 1) for v in node]
    return node


def parse_spec(text):
    """Parse raw spec text -> dict with openapi_version, info, contract.

    Raises SpecParseError on invalid input. `contract` is the fully
    $ref-expanded deep copy safe to store as JSON.
    """
    data = _load_spec(text)
    _check_openapi(data)
    info = data.get("info", {})
    contract = _expand_refs(data, data)
    # round-trip through JSON to guarantee JSONField-serializable content
    contract = json.loads(json.dumps(contract))
    return {
        "openapi_version": str(data["openapi"]),
        "title": info.get("title", ""),
        "version": str(info["version"]),
        "contract": contract,
    }

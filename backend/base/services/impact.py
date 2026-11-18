"""Impact analysis (FR-06): join breaking changes against declared consumer usage.

Purely static, per the agreed design: a consumer is affected when it
*declared* a use matching the change (same provider, method, normalized
path) and depends on the changed field (sends for request-side changes,
reads for response-side changes). Endpoint-level changes (endpoint or
method removed, path renamed) affect every consumer that declared the use,
regardless of which fields it listed.

Field matching is segment-prefix aware: removing `premium.breakdown`
affects a consumer that reads `premium.breakdown[].amount`; removing
`premium` affects one that reads `premium.total`.
"""
from base.models import (
    ChangeSide,
    ConsumerUse,
    DependencyDirection,
    ImpactItem,
    ImpactReport,
)
from base.services.differ import normalize_path


def _paths_match(a, b):
    return normalize_path(a) == normalize_path(b)


def _field_match(changed, dep):
    """True when `dep` is the changed path or lives inside/outside it."""
    if changed == dep:
        return True
    return (
        dep.startswith(changed + ".")
        or dep.startswith(changed + "[]")
        or changed.startswith(dep + ".")
        or changed.startswith(dep + "[]")
    )


def _direction_for(change):
    if change.side == ChangeSide.REQUEST:
        return DependencyDirection.SENDS
    if change.side == ChangeSide.RESPONSE:
        return DependencyDirection.READS
    return None


def _use_matches(use, change):
    if not _paths_match(use.path, change.path):
        return False
    if change.method and use.method.upper() != change.method.upper():
        return False
    return True


def analyze_impact(comparison):
    """Return [(change, consumer, use, dep_path_or_None)] without persisting."""
    breaking = list(comparison.changes.filter(breaking=True))
    if not breaking:
        return []
    uses = list(
        ConsumerUse.objects.filter(provider_service=comparison.base_version.service)
        .select_related("consumer")
        .prefetch_related("field_dependencies")
    )
    hits = []
    for change in breaking:
        direction = _direction_for(change)
        for use in uses:
            if not _use_matches(use, change):
                continue
            if not change.field_path:
                # endpoint/method/whole-path level change: the use itself is gone/renamed
                hits.append((change, use.consumer, use, None))
                continue
            for dep in use.field_dependencies.all():
                if direction and dep.direction != direction:
                    continue
                if _field_match(change.field_path, dep.field_path):
                    hits.append((change, use.consumer, use, dep.field_path))
    return hits


def create_impact_report(comparison):
    """Persist an ImpactReport + ImpactItems for `comparison` (FR-06, FR-08).

    Returns (report, hits). One item per (change, consumer) pair; `reason`
    carries the human explanation (NFR-07).
    """
    hits = analyze_impact(comparison)
    report = ImpactReport.objects.create(comparison=comparison)
    seen, items = set(), []
    for change, consumer, use, dep in hits:
        key = (change.id, consumer.id)
        if key in seen:
            continue
        seen.add(key)
        if dep:
            direction = _direction_for(change)
            word = direction if direction else "uses"
            reason = f"declares {use.method.upper()} {use.path} ({word} {dep}) — {change.explanation}"
        else:
            reason = f"declares {use.method.upper() or use.path} — {change.explanation}"
        items.append(ImpactItem(report=report, change=change, consumer=consumer, reason=reason))
    ImpactItem.objects.bulk_create(items)
    return report, hits

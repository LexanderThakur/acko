"""Publishing workflow endpoints (FR-07, FR-08).

Gate rule (MVP): attempting to publish a spec version compares it against
the currently published version (fallback: latest earlier version; none ->
first version, publishes immediately). If any breaking change affects a
registered consumer, the attempt is BLOCKED and an ImpactReport is stored;
otherwise it is APPROVED and the version becomes the service's published
one. Blocked/rejected attempts never touch the published version (NFR-02).
Every attempt and decision sends a webhook notification (FR-10).
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import (
    APIChange,
    APIComparison,
    AttemptStatus,
    Notification,
    PublishingAttempt,
    SpecStatus,
    SpecVersion,
)
from base.serializers.attempt_serializers import (
    AttemptCreateInSerializer,
    AttemptDecisionInSerializer,
    AttemptOutSerializer,
    attempt_out,
)
from base.services.differ import compare_contracts
from base.services.impact import create_impact_report
from base.services.notify import send_webhook
from base.views.sns_views import ListPagination


def _notify(request, attempt, event, blocked_reasons, affected_consumers):
    from django.conf import settings

    payload = {
        "event": event,
        "service": attempt.service.name,
        "version": attempt.spec_version.version,
        "attempt_id": attempt.id,
        "status": attempt.status,
        "blocked_reasons": blocked_reasons,
        "affected_consumers": affected_consumers,
    }
    # default: this server's own built-in receiver (project-contained);
    # WEBHOOK_RECEIVER_URL overrides to an external one (kit :9900)
    url = settings.WEBHOOK_RECEIVER_URL or request.build_absolute_uri("/api/webhook-events/receive/")
    delivered, response_status = send_webhook(payload, url=url)
    Notification.objects.create(
        attempt=attempt,
        payload=payload,
        receiver_url=url,
        delivered=delivered,
        response_status=response_status,
    )


def _base_version_for(spec: SpecVersion):
    """The version to diff against: the latest upload made BEFORE this one
    (published version preferred among them). Never a newer version, and
    never the spec itself."""
    earlier = spec.service.spec_versions.filter(pk__lt=spec.pk).order_by("-pk")
    published = earlier.filter(status=SpecStatus.PUBLISHED).first()
    return published or earlier.first()


def _get_or_create_comparison(base: SpecVersion, target: SpecVersion) -> APIComparison:
    comparison = (
        APIComparison.objects.filter(target_version=target).order_by("-created_at").first()
    )
    if comparison and comparison.base_version_id == base.pk:
        return comparison
    comparison = APIComparison.objects.create(base_version=base, target_version=target)
    detected = compare_contracts(base.contract or {}, target.contract or {})
    APIChange.objects.bulk_create(
        [
            APIChange(
                comparison=comparison,
                path=c["path"],
                method=c["method"],
                field_path=c["field_path"],
                side=c["side"],
                change_type=c["change_type"],
                severity=c["severity"],
                breaking=c["breaking"],
                explanation=c["explanation"],
                old_value=c["old_value"],
                new_value=c["new_value"],
            )
            for c in detected
        ]
    )
    return comparison


def _publish(spec: SpecVersion):
    """Make `spec` the service's single published version (NFR-02)."""
    spec.service.spec_versions.exclude(pk=spec.pk).filter(status=SpecStatus.PUBLISHED).update(
        status=SpecStatus.DRAFT
    )
    spec.status = SpecStatus.PUBLISHED
    spec.save(update_fields=["status"])


@extend_schema_view(
    post=extend_schema(
        request=AttemptCreateInSerializer,
        responses={
            201: AttemptOutSerializer,
            400: OpenApiResponse(description="Version already published"),
        },
        summary="Attempt to publish a spec version (auto-approved unless consumers are affected)",
        operation_id="attempts_create",
    ),
    get=extend_schema(
        responses={200: AttemptOutSerializer(many=True)},
        summary="List publishing attempts with outcomes (history)",
        operation_id="attempts_list",
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def publishing_attempts(request):
    if request.method == "GET":
        paginator = ListPagination()
        page = paginator.paginate_queryset(
            PublishingAttempt.objects.select_related(
                "service", "spec_version", "comparison", "impact_report"
            ).order_by("-created_at"),
            request,
            view=None,
        )
        return paginator.get_paginated_response([attempt_out(a) for a in page])

    serializer = AttemptCreateInSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    spec = get_object_or_404(
        SpecVersion.objects.select_related("service"), id=serializer.validated_data["spec_version_id"]
    )
    if spec.status == SpecStatus.PUBLISHED:
        return Response(
            {"detail": f"version {spec.version} is already published"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    base = _base_version_for(spec)
    comparison = report = None
    affected, reasons = [], []

    if base is not None:
        comparison = _get_or_create_comparison(base, spec)
        report, hits = create_impact_report(comparison)
        affected = sorted({h[1].name for h in hits})
        reasons = _reasons(report)

    with transaction.atomic():
        if not affected:
            _publish(spec)
            attempt_status = AttemptStatus.APPROVED
        else:
            spec.status = SpecStatus.BLOCKED
            spec.save(update_fields=["status"])
            attempt_status = AttemptStatus.BLOCKED

        attempt = PublishingAttempt.objects.create(
            service=spec.service,
            spec_version=spec,
            status=attempt_status,
            comparison=comparison,
            impact_report=report,
        )

    _notify(
        request,
        attempt,
        "publish.approved" if attempt_status == AttemptStatus.APPROVED else "publish.blocked",
        reasons,
        affected,
    )
    return Response(attempt_out(attempt), status=status.HTTP_201_CREATED)


def _reasons(report):
    if report is None:
        return []
    return list(report.items.values_list("reason", flat=True))


@extend_schema(
    request=AttemptDecisionInSerializer,
    responses={200: AttemptOutSerializer, 400: OpenApiResponse(description="Attempt is not blocked")},
    summary="Approve a blocked attempt (publishes the version)",
    operation_id="attempts_approve",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def attempt_approve(request, attempt_id):
    attempt = get_object_or_404(
        PublishingAttempt.objects.select_related("service", "spec_version"), id=attempt_id
    )
    if attempt.status != AttemptStatus.BLOCKED:
        return Response(
            {"detail": f"only blocked attempts can be approved (this one is '{attempt.status}')"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = AttemptDecisionInSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        _publish(attempt.spec_version)
        attempt.status = AttemptStatus.APPROVED
        attempt.decided_by = request.user
        attempt.decided_at = timezone.now()
        attempt.comment = serializer.validated_data.get("comment", "")
        attempt.save()

    _notify(request, attempt, "publish.approved", _reasons(attempt.impact_report), _affected(attempt))
    return Response(attempt_out(attempt))


@extend_schema(
    request=AttemptDecisionInSerializer,
    responses={200: AttemptOutSerializer, 400: OpenApiResponse(description="Attempt is not blocked")},
    summary="Reject a blocked attempt (version stays unpublished)",
    operation_id="attempts_reject",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def attempt_reject(request, attempt_id):
    attempt = get_object_or_404(
        PublishingAttempt.objects.select_related("service", "spec_version"), id=attempt_id
    )
    if attempt.status != AttemptStatus.BLOCKED:
        return Response(
            {"detail": f"only blocked attempts can be rejected (this one is '{attempt.status}')"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = AttemptDecisionInSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)

    attempt.status = AttemptStatus.REJECTED
    attempt.decided_by = request.user
    attempt.decided_at = timezone.now()
    attempt.comment = serializer.validated_data.get("comment", "")
    attempt.save()
    attempt.spec_version.status = SpecStatus.DRAFT
    attempt.spec_version.save(update_fields=["status"])

    _notify(request, attempt, "publish.rejected", _reasons(attempt.impact_report), _affected(attempt))
    return Response(attempt_out(attempt))


def _affected(attempt):
    if attempt.impact_report is None:
        return []
    return sorted({i.consumer.name for i in attempt.impact_report.items.select_related("consumer")})

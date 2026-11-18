"""Serializers for the PublishingAttempt API (FR-07, FR-08)."""
from rest_framework import serializers


class AttemptCreateInSerializer(serializers.Serializer):
    spec_version_id = serializers.IntegerField(help_text="SpecVersion to publish")


class AttemptDecisionInSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="", help_text="Reviewer note")


def attempt_out(attempt) -> dict:
    reasons, affected = [], []
    if attempt.impact_report is not None:
        items = attempt.impact_report.items.select_related("change", "consumer")
        reasons = [i.reason for i in items]
        affected = sorted({i.consumer.name for i in items})
    return {
        "id": attempt.id,
        "service": attempt.service_id,
        "service_name": attempt.service.name,
        "spec_version": attempt.spec_version_id,
        "version": attempt.spec_version.version,
        "status": attempt.status,
        "comparison": attempt.comparison_id,
        "impact_report": attempt.impact_report_id,
        "blocked_reasons": reasons,
        "affected_consumers": affected,
        "decided_by": attempt.decided_by.username if attempt.decided_by else None,
        "decided_at": attempt.decided_at,
        "comment": attempt.comment,
        "created_at": attempt.created_at,
    }


class AttemptOutSerializer(serializers.Serializer):
    """Schema shape for docs; responses are built by attempt_out()."""

    id = serializers.IntegerField()
    service = serializers.IntegerField()
    service_name = serializers.CharField()
    spec_version = serializers.IntegerField()
    version = serializers.CharField()
    status = serializers.ChoiceField(choices=["approved", "blocked", "rejected"])
    comparison = serializers.IntegerField(allow_null=True)
    impact_report = serializers.IntegerField(allow_null=True)
    blocked_reasons = serializers.ListField(child=serializers.CharField())
    affected_consumers = serializers.ListField(child=serializers.CharField())
    decided_by = serializers.CharField(allow_null=True)
    decided_at = serializers.DateTimeField(allow_null=True)
    comment = serializers.CharField()
    created_at = serializers.DateTimeField()

"""Serializers for the Comparison and Change API (FR-03, FR-04)."""
from rest_framework import serializers

from base.models import APIChange, ChangeSide, ChangeType, ChangeSeverity


class ComparisonCreateSerializer(serializers.Serializer):
    """POST /comparisons/ body."""

    base_spec_id = serializers.IntegerField(help_text="SpecVersion id to compare from")
    target_spec_id = serializers.IntegerField(help_text="SpecVersion id to compare to")


class ChangeOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    path = serializers.CharField()
    method = serializers.CharField()
    field_path = serializers.CharField()
    side = serializers.ChoiceField(choices=ChangeSide.choices)
    change_type = serializers.ChoiceField(choices=ChangeType.choices)
    severity = serializers.ChoiceField(choices=ChangeSeverity.choices)
    breaking = serializers.BooleanField()
    explanation = serializers.CharField()
    old_value = serializers.JSONField(allow_null=True)
    new_value = serializers.JSONField(allow_null=True)
    location = serializers.CharField(help_text="e.g. 'POST /quotes premium.total'")

    def to_representation(self, instance: APIChange):
        return {
            "id": instance.id,
            "path": instance.path,
            "method": instance.method,
            "field_path": instance.field_path,
            "side": instance.side,
            "change_type": instance.change_type,
            "severity": instance.severity,
            "breaking": instance.breaking,
            "explanation": instance.explanation,
            "old_value": instance.old_value,
            "new_value": instance.new_value,
            "location": instance.location,
        }


def _comparison_out(cmp) -> dict:
    return {
        "id": cmp.id,
        "service": cmp.base_version.service_id,
        "service_name": cmp.base_version.service.name,
        "base_spec": cmp.base_version_id,
        "target_spec": cmp.target_version_id,
        "base_version": cmp.base_version.version,
        "target_version": cmp.target_version.version,
        "summary": cmp.summary,
        "breaking": cmp.changes.filter(breaking=True).count(),
        "created_at": cmp.created_at,
    }


class ComparisonOutSerializer(serializers.Serializer):
    """Comparison as returned in list views."""

    id = serializers.IntegerField()
    service = serializers.IntegerField()
    service_name = serializers.CharField()
    base_spec = serializers.IntegerField()
    target_spec = serializers.IntegerField()
    base_version = serializers.CharField()
    target_version = serializers.CharField()
    summary = serializers.JSONField()
    breaking = serializers.IntegerField()
    created_at = serializers.DateTimeField()

    def to_representation(self, instance):
        return _comparison_out(instance)


class ComparisonDetailOutSerializer(ComparisonOutSerializer):
    """Comparison plus all its detected changes (blockers first)."""

    changes = ChangeOutSerializer(many=True)

    def to_representation(self, instance):
        from base.services.differ import sort_changes

        data = _comparison_out(instance)
        ordered = sort_changes([
            {
                "id": c.id,
                "path": c.path, "method": c.method, "field_path": c.field_path,
                "side": c.side, "change_type": c.change_type, "severity": c.severity,
                "breaking": c.breaking, "explanation": c.explanation,
                "old_value": c.old_value, "new_value": c.new_value,
                "location": c.location,
            }
            for c in instance.changes.all()
        ])
        data["changes"] = ordered
        return data

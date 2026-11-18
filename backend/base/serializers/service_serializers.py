"""Serializers for the Service and SpecVersion API (FR-01, FR-02).

Request serializers define exactly what Swagger UI asks for; response
serializers shape what comes back. Written so every field is explicit —
no ModelSerializer field-guessing — keeping the schema predictable.
"""
from rest_framework import serializers

from base.models import Service, SpecVersion, SpecStatus


class ServiceCreateSerializer(serializers.Serializer):
    """POST /services/ body."""

    name = serializers.CharField(max_length=100, help_text="Unique service name, e.g. quote-api")
    owner_team = serializers.CharField(max_length=100, help_text="Owning team, e.g. Quotes team")
    description = serializers.CharField(required=False, allow_blank=True, default="")


class ServiceOutSerializer(serializers.Serializer):
    """Service as returned in lists and detail views."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    owner_team = serializers.CharField()
    description = serializers.CharField()
    published_version = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


def _to_spec_out(spec: SpecVersion) -> dict:
    return {
        "id": spec.id,
        "service": spec.service_id,
        "version": spec.version,
        "status": spec.status,
        "title": (spec.contract or {}).get("title", ""),
        "openapi_version": (spec.contract or {}).get("openapi_version", ""),
        "created_at": spec.created_at,
    }


class SpecOutSerializer(serializers.Serializer):
    """SpecVersion metadata as returned in lists/detail (raw spec not included)."""

    id = serializers.IntegerField()
    service = serializers.IntegerField()
    version = serializers.CharField()
    status = serializers.ChoiceField(choices=SpecStatus.choices)
    title = serializers.CharField()
    openapi_version = serializers.CharField()
    created_at = serializers.DateTimeField()

    def to_representation(self, instance):
        return _to_spec_out(instance)


class SpecDetailOutSerializer(SpecOutSerializer):
    """SpecVersion metadata plus the raw uploaded spec text."""

    spec = serializers.CharField()
    contract = serializers.JSONField()

    def to_representation(self, instance):
        data = _to_spec_out(instance)
        data["spec"] = instance.spec
        data["contract"] = instance.contract
        return data


class SpecUploadSerializer(serializers.Serializer):
    """POST /services/{id}/specs/ body: raw YAML/JSON text or an uploaded file.

    Both fields are optional; provide exactly one. A file upload wins over
    raw text, so dragging a file into Swagger UI just works.
    """

    spec_text = serializers.CharField(
        required=False,
        help_text="Raw OpenAPI 3.0 YAML or JSON text (or use the file field instead)",
        style={"base_template": "textarea.html"},
    )
    file = serializers.FileField(
        required=False,
        help_text="Upload a .yaml/.yml/.json OpenAPI file (or paste spec_text instead)",
    )

    def validate(self, attrs):
        if not attrs.get("file") and not attrs.get("spec_text"):
            raise serializers.ValidationError("provide either 'file' or 'spec_text'")
        return attrs

"""Serializers for the Consumer registry API (FR-05).

The request shape intentionally matches the starter kit's consumer files
({consumer, team, uses: [{provider, method, path, sends, reads}]}) so a
kit file converts to a request body by YAML->JSON alone.
"""
from rest_framework import serializers

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}


class ConsumerUseInSerializer(serializers.Serializer):
    provider = serializers.CharField(help_text="Provider service name, e.g. quote-api")
    method = serializers.CharField(help_text="HTTP method, e.g. POST")
    path = serializers.CharField(help_text="Path template, e.g. /quotes/{id}")
    sends = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
        help_text="Request fields/parameters this consumer sends",
    )
    reads = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
        help_text="Response fields this consumer reads",
    )


class ConsumerInSerializer(serializers.Serializer):
    consumer = serializers.CharField(required=False, help_text="Consumer service name, e.g. mobile-app")
    name = serializers.CharField(required=False, help_text="Alias of 'consumer' (either works)")
    team = serializers.CharField(help_text="Owning team, e.g. Mobile")
    uses = ConsumerUseInSerializer(many=True, required=False)

    def validate(self, attrs):
        if not attrs.get("consumer") and not attrs.get("name"):
            raise serializers.ValidationError("provide 'consumer' (or alias 'name')")
        return attrs

    def get_name(self, validated):
        return validated.get("consumer") or validated.get("name")


class ConsumerOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    team = serializers.CharField()
    uses = serializers.ListField()


def consumer_out(consumer) -> dict:
    uses = []
    for use in consumer.uses.all():
        deps = list(use.field_dependencies.order_by("field_path"))
        uses.append(
            {
                "id": use.id,
                "provider": use.provider_service.name,
                "provider_id": use.provider_service_id,
                "method": use.method,
                "path": use.path,
                "sends": [d.field_path for d in deps if d.direction == "sends"],
                "reads": [d.field_path for d in deps if d.direction == "reads"],
            }
        )
    return {
        "id": consumer.id,
        "name": consumer.name,
        "team": consumer.team,
        "uses": uses,
    }

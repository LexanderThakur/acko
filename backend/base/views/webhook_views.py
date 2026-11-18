"""Built-in webhook receiver (FR-10).

Stands in for chat/email/paging so the whole system is self-contained:
publishing notifications are POSTed here by default (no second server
needed). GET lists what arrived, DELETE clears it. Setting
WEBHOOK_RECEIVER_URL points notifications elsewhere (e.g. the starter
kit's receiver on :9900) with no code change.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from base.models import WebhookEvent


class WebhookEventOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    received_at = serializers.DateTimeField()
    path = serializers.CharField()
    body = serializers.JSONField()


@extend_schema(
    request=None,  # any JSON payload
    responses={201: {"type": "object", "properties": {"ok": {"type": "boolean"}, "id": {"type": "integer"}}}},
    summary="Webhook receiver: record a notification payload (no auth, like an external receiver)",
    operation_id="webhook_receive",
)
@api_view(["POST"])
@permission_classes([])
def webhook_receive(request):
    body = request.data
    event = WebhookEvent.objects.create(
        path=request.path,
        body=body if isinstance(body, dict) else {"raw": str(body)},
    )
    return Response({"ok": True, "id": event.id}, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        responses={200: WebhookEventOutSerializer(many=True)},
        summary="List received webhook events (newest first)",
        operation_id="webhook_events_list",
    ),
    delete=extend_schema(
        responses={200: {"type": "object", "properties": {"ok": {"type": "boolean"}}}},
        summary="Clear all received webhook events",
        operation_id="webhook_events_clear",
    ),
)
@api_view(["GET", "DELETE"])
@permission_classes([])
def webhook_events(request):
    if request.method == "GET":
        events = WebhookEvent.objects.all()[:100]
        return Response(
            [WebhookEventOutSerializer({
                "id": e.id, "received_at": e.received_at, "path": e.path, "body": e.body,
            }).data for e in events]
        )
    count, _ = WebhookEvent.objects.all().delete()
    return Response({"ok": True, "cleared": count})

"""Consumer registry endpoints (FR-05).

Registering a consumer with an existing name replaces its declared uses
(idempotent re-registration — re-posting a kit consumer file refreshes it).
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import APIConsumer, ConsumerUse, DependencyDirection, FieldDependency, Service
from base.serializers.consumer_serializers import (
    ConsumerInSerializer,
    ConsumerOutSerializer,
    HTTP_METHODS,
    consumer_out,
)
from base.views.sns_views import ListPagination


def _create_uses(consumer, uses_data):
    """Create ConsumerUse + FieldDependency rows (dedup, validated data)."""
    for use_data in uses_data:
        provider = Service.objects.get(name__iexact=use_data["provider"])
        use = ConsumerUse.objects.create(
            consumer=consumer,
            provider_service=provider,
            method=use_data["method"].upper(),
            path=use_data["path"],
        )
        deps = [
            FieldDependency(use=use, direction=direction, field_path=field_path)
            for direction, key in (
                (DependencyDirection.SENDS, "sends"),
                (DependencyDirection.READS, "reads"),
            )
            for field_path in dict.fromkeys(use_data[key])  # dedupe, keep order
        ]
        FieldDependency.objects.bulk_create(deps)


@extend_schema_view(
    post=extend_schema(
        request=ConsumerInSerializer,
        responses={
            201: ConsumerOutSerializer,
            400: OpenApiResponse(description="Unknown provider service or invalid method/path"),
        },
        summary="Register a consumer with its declared endpoint uses and field dependencies",
        operation_id="consumers_create",
    ),
    get=extend_schema(
        responses={200: ConsumerOutSerializer(many=True)},
        summary="List consumers with their declared uses",
        operation_id="consumers_list",
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def consumers(request):
    if request.method == "GET":
        paginator = ListPagination()
        page = paginator.paginate_queryset(
            APIConsumer.objects.prefetch_related("uses__provider_service", "uses__field_dependencies"),
            request,
            view=None,
        )
        return paginator.get_paginated_response([consumer_out(c) for c in page])

    serializer = ConsumerInSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data
    name = serializer.get_name(validated)
    uses_data = validated.get("uses") or []

    # validate providers and methods up-front for an all-or-nothing result
    errors = []
    for i, use_data in enumerate(uses_data):
        if not Service.objects.filter(name__iexact=use_data["provider"]).exists():
            errors.append(f"uses[{i}].provider: unknown service '{use_data['provider']}'")
        if use_data["method"].upper() not in HTTP_METHODS:
            errors.append(f"uses[{i}].method: invalid HTTP method '{use_data['method']}'")
        if not use_data["path"].startswith("/"):
            errors.append(f"uses[{i}].path: must start with '/'")
    if errors:
        return Response({"uses": errors}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        consumer, _ = APIConsumer.objects.get_or_create(name__iexact=name, defaults={"name": name, "team": validated["team"]})
        consumer.team = validated["team"]
        consumer.save(update_fields=["team"])
        consumer.uses.all().delete()  # idempotent re-registration
        _create_uses(consumer, uses_data)

    consumer.refresh_from_db()
    return Response(consumer_out(consumer), status=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: ConsumerOutSerializer},
    summary="Consumer detail",
    operation_id="consumers_retrieve",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consumer_detail(request, consumer_id):
    consumer = get_object_or_404(
        APIConsumer.objects.prefetch_related("uses__provider_service", "uses__field_dependencies"),
        id=consumer_id,
    )
    return Response(consumer_out(consumer))

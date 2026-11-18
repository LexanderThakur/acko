"""Comparison endpoints: diff two spec versions, list and detail (FR-03, FR-04)."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import APIChange, APIComparison, SpecVersion
from base.serializers.comparison_serializers import (
    ComparisonCreateSerializer,
    ComparisonDetailOutSerializer,
    ComparisonOutSerializer,
)
from base.services.differ import compare_contracts
from base.views.sns_views import ListPagination


def _comparison_payload(comparison) -> dict:
    from base.serializers.comparison_serializers import _comparison_out

    return _comparison_out(comparison)


@extend_schema_view(
    post=extend_schema(
        request=ComparisonCreateSerializer,
        responses={
            201: ComparisonOutSerializer,
            400: OpenApiResponse(description="Specs must belong to the same service"),
        },
        summary="Compare two spec versions and store the detected changes",
        operation_id="comparisons_create",
    ),
    get=extend_schema(
        responses={200: ComparisonOutSerializer(many=True)},
        summary="List comparisons (optionally filter with ?service={id})",
        operation_id="comparisons_list",
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def comparisons(request):
    if request.method == "GET":
        queryset = APIComparison.objects.select_related(
            "base_version__service", "target_version__service"
        ).order_by("-created_at")
        service_id = request.query_params.get("service")
        if service_id and service_id.isdigit():
            queryset = queryset.filter(base_version__service_id=service_id)

        paginator = ListPagination()
        page = paginator.paginate_queryset(queryset, request, view=None)
        return paginator.get_paginated_response([_comparison_payload(c) for c in page])

    serializer = ComparisonCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    base = get_object_or_404(SpecVersion.objects.select_related("service"), id=data["base_spec_id"])
    target = get_object_or_404(SpecVersion.objects.select_related("service"), id=data["target_spec_id"])

    if base.service_id != target.service_id:
        return Response(
            {"detail": f"specs must belong to the same service ('{base.service.name}' vs '{target.service.name}')"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    detected = compare_contracts(base.contract or {}, target.contract or {})

    with transaction.atomic():
        comparison = APIComparison.objects.create(base_version=base, target_version=target)
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

    return Response(_comparison_payload(comparison), status=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: ComparisonDetailOutSerializer},
    summary="Comparison detail with all detected changes (blockers first)",
    operation_id="comparisons_retrieve",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def comparison_detail(request, comparison_id):
    comparison = get_object_or_404(
        APIComparison.objects.select_related("base_version__service", "target_version__service"),
        id=comparison_id,
    )
    out = ComparisonDetailOutSerializer()
    return Response(out.to_representation(comparison))

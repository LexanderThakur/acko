"""Service registry and spec upload endpoints (FR-01, FR-02)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Service, SpecVersion, SpecStatus
from base.serializers.service_serializers import (
    ServiceCreateSerializer,
    ServiceOutSerializer,
    SpecDetailOutSerializer,
    SpecOutSerializer,
    SpecUploadSerializer,
)
from base.services.spec_parser import SpecParseError, parse_spec


class ListPagination(PageNumberPagination):
    page_size = 50


@extend_schema(
    responses={200: {"type": "object", "properties": {"ok": {"type": "boolean"}}}},
    summary="Liveness probe (no auth) — used by the container healthcheck / load balancers",
    operation_id="health",
)
@api_view(["GET"])
@permission_classes([])
def health(request):
    return Response({"ok": True})


def _published_version(service: Service):
    published = service.spec_versions.filter(status=SpecStatus.PUBLISHED).first()
    return published.version if published else None


def _service_out(service: Service) -> dict:
    data = ServiceOutSerializer(
        {
            "id": service.id,
            "name": service.name,
            "owner_team": service.owner_team,
            "description": service.description,
            "published_version": _published_version(service),
            "created_at": service.created_at,
        }
    )
    return data.data


@extend_schema_view(
    post=extend_schema(
        request=ServiceCreateSerializer,
        responses={201: ServiceOutSerializer, 400: OpenApiResponse(description="Name already registered")},
        summary="Register a service",
        operation_id="services_create",
    ),
    get=extend_schema(
        responses={200: ServiceOutSerializer(many=True)},
        summary="List registered services",
        operation_id="services_list",
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def services(request):
    if request.method == "GET":
        paginator = ListPagination()
        objs = paginator.paginate_queryset(Service.objects.all(), request, view=None)
        return paginator.get_paginated_response([_service_out(s) for s in objs])

    serializer = ServiceCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if Service.objects.filter(name__iexact=data["name"]).exists():
        return Response({"name": ["service name already registered"]}, status=status.HTTP_400_BAD_REQUEST)
    service = Service.objects.create(**data)
    return Response(_service_out(service), status=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: ServiceOutSerializer},
    summary="Service detail",
    operation_id="services_retrieve",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_detail(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    return Response(_service_out(service))


@extend_schema_view(
    post=extend_schema(
        request=SpecUploadSerializer,
        responses={
            201: SpecOutSerializer,
            400: OpenApiResponse(description="Invalid YAML/JSON, not OpenAPI 3.0.x, or missing info.version"),
        },
        summary="Upload a new spec version for this service (YAML/JSON text or file)",
        operation_id="specs_upload",
    ),
    get=extend_schema(
        responses={200: SpecOutSerializer(many=True)},
        summary="List this service's spec versions",
        operation_id="specs_list",
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def service_specs(request, service_id):
    service = get_object_or_404(Service, id=service_id)

    if request.method == "GET":
        paginator = ListPagination()
        specs = paginator.paginate_queryset(
            service.spec_versions.order_by("created_at"), request, view=None
        )
        return paginator.get_paginated_response([SpecOutSerializer().to_representation(s) for s in specs])

    # POST: upload a new spec version
    body = {}
    if request.FILES.get("file"):
        body["file"] = request.FILES["file"]
    if isinstance(request.data, dict) and request.data.get("spec_text"):
        body["spec_text"] = request.data["spec_text"]
    serializer = SpecUploadSerializer(data=body)
    serializer.is_valid(raise_exception=True)

    if serializer.validated_data.get("file"):
        raw = serializer.validated_data["file"].read()
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
    else:
        text = serializer.validated_data["spec_text"]

    try:
        parsed = parse_spec(text)
    except SpecParseError as e:
        return Response({"spec": [e.message]}, status=status.HTTP_400_BAD_REQUEST)

    spec_version = SpecVersion.objects.create(
        service=service,
        version=parsed["version"],
        spec=text,
        contract={"openapi_version": parsed["openapi_version"], "title": parsed["title"], **parsed["contract"]},
    )
    return Response(SpecOutSerializer().to_representation(spec_version), status=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: SpecDetailOutSerializer},
    summary="Spec version detail (includes raw spec and expanded contract)",
    operation_id="specs_retrieve",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def spec_detail(request, service_id, spec_id):
    spec = get_object_or_404(SpecVersion, id=spec_id, service_id=service_id)
    return Response(SpecDetailOutSerializer().to_representation(spec))

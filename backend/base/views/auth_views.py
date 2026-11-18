"""Auth endpoints: register, login (JWT access token) and current user (NFR-04).

Function-based views with api_view + drf-spectacular decorators. No refresh
tokens: the access token is all we issue — when it expires, log in again.
Login validates through simplejwt's TokenObtainPairSerializer so token
creation stays stock, but only the access token is returned.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt import serializers as jwt_serializers
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")


class RegisterResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    access = serializers.CharField()


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()


@extend_schema(
    request=RegisterRequestSerializer,
    responses={201: RegisterResponseSerializer},
    auth=[],
    summary="Register a new user (returns an access token)",
    operation_id="auth_register",
)
@api_view(["POST"])
@permission_classes([])
def register(request):
    serializer = RegisterRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        django_validate_password(data["password"])
    except DjangoValidationError as e:
        return Response({"password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username__iexact=data["username"]).exists():
        return Response({"username": ["username already taken"]}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=data["username"], email=data.get("email") or "", password=data["password"]
    )
    access = RefreshToken.for_user(user).access_token
    out = RegisterResponseSerializer(
        {"id": user.id, "username": user.username, "access": str(access)}
    )
    return Response(out.data, status=status.HTTP_201_CREATED)


@extend_schema(
    request=LoginRequestSerializer,
    responses={200: TokenResponseSerializer},
    auth=[],
    summary="Log in with username/password (returns an access token)",
    operation_id="auth_login",
)
@api_view(["POST"])
@permission_classes([])
def login(request):
    serializer = jwt_serializers.TokenObtainPairSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response({"access": serializer.validated_data["access"]}, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: MeSerializer},
    summary="Current user",
    operation_id="auth_me",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response(
        MeSerializer({"id": user.id, "username": user.username, "email": user.email or ""}).data,
        status=status.HTTP_200_OK,
    )

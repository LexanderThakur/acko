from django.urls import path

from base.views import auth_views, comparison_views, consumer_views, publishing_views, sns_views, webhook_views

urlpatterns = [
    # Auth (NFR-04): access-token only — log in again when it expires.
    path("auth/register/", auth_views.register, name="auth_register"),
    path("auth/login/", auth_views.login, name="auth_login"),
    path("auth/me/", auth_views.me, name="auth_me"),

    # Services & specs (FR-01, FR-02)
    path("services/", sns_views.services, name="services"),
    path("services/<int:service_id>/", sns_views.service_detail, name="service_detail"),
    path("services/<int:service_id>/specs/", sns_views.service_specs, name="service_specs"),
    path("services/<int:service_id>/specs/<int:spec_id>/", sns_views.spec_detail, name="spec_detail"),

    # Comparisons & changes (FR-03, FR-04)
    path("comparisons/", comparison_views.comparisons, name="comparisons"),
    path("comparisons/<int:comparison_id>/", comparison_views.comparison_detail, name="comparison_detail"),

    # Consumers (FR-05)
    path("consumers/", consumer_views.consumers, name="consumers"),
    path("consumers/<int:consumer_id>/", consumer_views.consumer_detail, name="consumer_detail"),

    # Publishing workflow (FR-07, FR-08)
    path("publishing-attempts/", publishing_views.publishing_attempts, name="publishing_attempts"),
    path("publishing-attempts/<int:attempt_id>/approve/", publishing_views.attempt_approve, name="attempt_approve"),
    path("publishing-attempts/<int:attempt_id>/reject/", publishing_views.attempt_reject, name="attempt_reject"),

    # Built-in webhook receiver (FR-10)
    path("webhook-events/", webhook_views.webhook_events, name="webhook_events"),
    path("webhook-events/receive/", webhook_views.webhook_receive, name="webhook_receive"),

    # Ops
    path("health/", sns_views.health, name="health"),
]

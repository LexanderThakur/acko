"""Core entities for Contract Guard (see Plan.md).

User is Django's built-in auth user (JWT via simplejwt) — no custom model.
Everything here is SQLite-friendly and intentionally minimal.
"""
from django.conf import settings
from django.db import models


class SpecStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    BLOCKED = "blocked", "Blocked"


class DependencyDirection(models.TextChoices):
    SENDS = "sends", "Sends"
    READS = "reads", "Reads"


class ChangeType(models.TextChoices):
    ENDPOINT_REMOVED = "endpoint_removed", "Endpoint removed"
    PATH_ADDED = "path_added", "Endpoint added"
    METHOD_REMOVED = "method_removed", "Method removed"
    METHOD_ADDED = "method_added", "Method added"
    FIELD_REMOVED = "field_removed", "Field removed or renamed"
    FIELD_ADDED = "field_added", "Field added"
    FIELD_TYPE_CHANGED = "field_type_changed", "Field type changed"
    REQUIRED_ADDED = "required_added", "Field made required"
    REQUIRED_REMOVED = "required_removed", "Field made optional"
    PATH_PARAM_CHANGED = "path_param_changed", "Path parameter changed"
    RESPONSE_REMOVED = "response_removed", "Response status code removed"
    METADATA_CHANGED = "metadata_changed", "Metadata changed"


class ChangeSide(models.TextChoices):
    REQUEST = "request", "Request"
    RESPONSE = "response", "Response"
    NONE = "none", "Not applicable"


class ChangeSeverity(models.TextChoices):
    BLOCKER = "blocker", "Blocker"
    MAJOR = "major", "Major"
    MINOR = "minor", "Minor"
    INFO = "info", "Info"


class AttemptStatus(models.TextChoices):
    BLOCKED = "blocked", "Blocked"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Service(models.Model):
    """A provider microservice that owns an API contract (FR-01)."""

    name = models.CharField(max_length=100, unique=True)
    owner_team = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.owner_team})"


class SpecVersion(models.Model):
    """One uploaded OpenAPI specification of a Service (FR-01, FR-02).

    `spec` keeps the raw YAML/JSON text; `contract` stores the normalized
    contract with internal $refs expanded, so comparisons work on the real
    contract rather than file layout (FR-02).

    Duplicate version numbers are allowed on purpose: re-publishing an
    existing version number with different content is exactly the kind of
    unsafe attempt Contract Guard must detect (the kit's claims-api trap).
    """

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="spec_versions")
    version = models.CharField(max_length=50)
    spec = models.TextField()  # raw YAML/JSON as uploaded
    contract = models.JSONField(default=dict, blank=True)  # $ref-expanded contract
    status = models.CharField(max_length=20, choices=SpecStatus.choices, default=SpecStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["service", "created_at"]
        constraints = [
            # NFR-02: only one published version per service at any time.
            models.UniqueConstraint(
                fields=["service"],
                condition=models.Q(status=SpecStatus.PUBLISHED),
                name="unique_published_spec_per_service",
            ),
        ]

    def __str__(self):
        return f"{self.service.name} {self.version} [{self.status}]"


class APIConsumer(models.Model):
    """A consuming service that calls other services' APIs (FR-05)."""

    name = models.CharField(max_length=100, unique=True)
    team = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.team})"


class ConsumerUse(models.Model):
    """One endpoint of one provider service that an APIConsumer calls (FR-05)."""

    consumer = models.ForeignKey(APIConsumer, on_delete=models.CASCADE, related_name="uses")
    provider_service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="consumer_uses")
    method = models.CharField(max_length=10)  # GET, POST, ...
    path = models.CharField(max_length=300)  # template, e.g. /quotes/{quoteId}

    class Meta:
        ordering = ["consumer__name", "provider_service__name", "path"]
        constraints = [
            models.UniqueConstraint(
                fields=["consumer", "provider_service", "method", "path"],
                name="unique_consumer_use",
            ),
        ]

    def __str__(self):
        return f"{self.consumer.name} -> {self.method} {self.path} @ {self.provider_service.name}"


class FieldDependency(models.Model):
    """A single field path a consumer sends or reads for one ConsumerUse (FR-05, FR-06).

    Paths use dots for nesting and [] for list items, e.g. premium.breakdown[].amount.
    sends = request-side dependency, reads = response-side dependency.
    """

    use = models.ForeignKey(ConsumerUse, on_delete=models.CASCADE, related_name="field_dependencies")
    direction = models.CharField(max_length=10, choices=DependencyDirection.choices)
    field_path = models.CharField(max_length=300)

    class Meta:
        ordering = ["use", "direction", "field_path"]
        constraints = [
            models.UniqueConstraint(
                fields=["use", "direction", "field_path"],
                name="unique_field_dependency",
            ),
        ]

    def __str__(self):
        return f"{self.direction} {self.field_path}"


class APIComparison(models.Model):
    """One diff run between two spec versions of the same Service (FR-03, FR-08)."""

    base_version = models.ForeignKey(SpecVersion, on_delete=models.CASCADE, related_name="comparisons_as_base")
    target_version = models.ForeignKey(SpecVersion, on_delete=models.CASCADE, related_name="comparisons_as_target")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.base_version} -> {self.target_version}"

    @property
    def summary(self):
        """Counts by severity, for list views and the dashboard (FR-09)."""
        counts = {sev: 0 for sev, _ in ChangeSeverity.choices}
        for change in self.changes.all():
            counts[change.severity] += 1
        return counts


class APIChange(models.Model):
    """A single detected change with severity and explanation (FR-03, FR-04).

    method / path / field_path are stored separately (not merged into one
    location string) so impact analysis (FR-06) can join changes against
    ConsumerUse + FieldDependency rows directly.
    """

    comparison = models.ForeignKey(APIComparison, on_delete=models.CASCADE, related_name="changes")
    path = models.CharField(max_length=300, blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")
    field_path = models.CharField(max_length=300, blank=True, default="")
    side = models.CharField(max_length=10, choices=ChangeSide.choices, default=ChangeSide.NONE)
    change_type = models.CharField(max_length=30, choices=ChangeType.choices)
    severity = models.CharField(max_length=10, choices=ChangeSeverity.choices)
    breaking = models.BooleanField()
    explanation = models.TextField()
    old_value = models.JSONField(blank=True, null=True)
    new_value = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["comparison", "path", "method", "field_path"]

    def __str__(self):
        where = " ".join(filter(None, [self.method, self.path, self.field_path]))
        return f"[{self.severity}] {self.change_type}: {where}".strip()

    @property
    def location(self):
        """Human-readable location, e.g. 'POST /quotes premium.total'."""
        return " ".join(filter(None, [self.method.upper() if self.method else "", self.path, self.field_path]))


class ImpactReport(models.Model):
    """Consumers affected by one comparison's breaking changes (FR-06)."""

    comparison = models.ForeignKey(APIComparison, on_delete=models.CASCADE, related_name="impact_reports")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Impact of {self.comparison}"


class ImpactItem(models.Model):
    """One affected consumer for one change, with the reason (FR-06)."""

    report = models.ForeignKey(ImpactReport, on_delete=models.CASCADE, related_name="items")
    change = models.ForeignKey(APIChange, on_delete=models.CASCADE, related_name="impact_items")
    consumer = models.ForeignKey(APIConsumer, on_delete=models.CASCADE, related_name="impact_items")
    reason = models.TextField()  # e.g. 'reads premium.total which was removed'

    class Meta:
        ordering = ["report", "consumer__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["report", "change", "consumer"],
                name="unique_impact_item",
            ),
        ]

    def __str__(self):
        return f"{self.consumer.name} affected by {self.change}"


class PublishingAttempt(models.Model):
    """A publish request for a spec version: blocked, approved or rejected (FR-07, FR-08)."""

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="publishing_attempts")
    spec_version = models.ForeignKey(SpecVersion, on_delete=models.CASCADE, related_name="publishing_attempts")
    status = models.CharField(max_length=20, choices=AttemptStatus.choices)
    comparison = models.ForeignKey(
        APIComparison, null=True, blank=True, on_delete=models.SET_NULL, related_name="attempt_usages"
    )
    impact_report = models.ForeignKey(
        ImpactReport, null=True, blank=True, on_delete=models.SET_NULL, related_name="attempt_usages"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publishing_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.service.name} {self.spec_version.version} [{self.status}]"


class Notification(models.Model):
    """Webhook notification sent for a publishing attempt, and its delivery outcome (FR-10)."""

    attempt = models.ForeignKey(PublishingAttempt, on_delete=models.CASCADE, related_name="notifications")
    payload = models.JSONField()
    receiver_url = models.CharField(max_length=500)
    delivered = models.BooleanField(default=False)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event} -> {self.receiver_url} ({'ok' if self.delivered else 'failed'})"

    @property
    def event(self):
        return self.payload.get("event", "unknown")


class WebhookEvent(models.Model):
    """An event received by the built-in webhook receiver endpoint (FR-10).

    Contract Guard ships its own receiver so the whole system runs without
    a second server; setting WEBHOOK_RECEIVER_URL (e.g. the starter kit's
    http://localhost:9900/contract-guard) swaps the destination without
    code changes.
    """

    received_at = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=300)
    body = models.JSONField()

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.path} @ {self.received_at:%H:%M:%S}"

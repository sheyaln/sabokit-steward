from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ImportJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        PREVIEW = "preview", _("Preview ready")
        RUNNING = "running", _("Running")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="import_jobs",
        verbose_name=_("uploaded by"),
    )
    original_filename = models.CharField(_("original filename"), max_length=255)
    csv = models.FileField(_("CSV"), upload_to="imports/")
    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.PENDING
    )
    summary = models.JSONField(_("summary"), default=dict, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("import job")
        verbose_name_plural = _("import jobs")

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.status})"


class ImportJobRow(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        SKIP = "skip", _("Skip")
        ERROR = "error", _("Error")

    job = models.ForeignKey(
        ImportJob, on_delete=models.CASCADE, related_name="rows", verbose_name=_("job")
    )
    row_number = models.PositiveIntegerField(_("row number"))
    email = models.EmailField(_("email"), blank=True)
    name = models.CharField(_("name"), max_length=255, blank=True)
    x_number = models.CharField(_("X-Number"), max_length=64, blank=True)
    action = models.CharField(_("action"), max_length=16, choices=Action.choices)
    message = models.CharField(_("message"), max_length=500, blank=True)
    authentik_pk = models.IntegerField(_("Authentik pk"), null=True, blank=True)
    applied = models.BooleanField(_("applied"), default=False)

    class Meta:
        ordering = ("row_number",)
        verbose_name = _("import job row")
        verbose_name_plural = _("import job rows")
        indexes = [models.Index(fields=("job", "action"))]

    def __str__(self) -> str:
        return f"row {self.row_number}: {self.action} {self.email}"

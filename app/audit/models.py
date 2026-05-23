from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    class Action(models.TextChoices):
        MEMBER_CREATE = "member.create", _("Member created")
        MEMBER_UPDATE = "member.update", _("Member updated")
        MEMBER_ACTIVATE = "member.activate", _("Member activated")
        MEMBER_DEACTIVATE = "member.deactivate", _("Member deactivated")
        MEMBER_PASSWORD_RESET = "member.password_reset", _("Password reset email sent")
        MEMBER_MFA_REMOVE = "member.mfa_remove", _("MFA device removed")
        GROUP_ADD = "group.add_member", _("Added to group")
        GROUP_REMOVE = "group.remove_member", _("Removed from group")
        IMPORT_CREATE = "import.create", _("Import created")
        IMPORT_RUN = "import.run", _("Import run")
        SETTINGS_UPDATE = "settings.update", _("Settings updated")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        verbose_name=_("actor"),
    )
    actor_username = models.CharField(_("actor username"), max_length=255, blank=True)
    action = models.CharField(_("action"), max_length=64, choices=Action.choices)
    target = models.CharField(_("target"), max_length=255, blank=True)
    before = models.JSONField(_("before"), null=True, blank=True)
    after = models.JSONField(_("after"), null=True, blank=True)
    note = models.CharField(_("note"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("audit event")
        verbose_name_plural = _("audit events")
        indexes = [
            models.Index(fields=("action", "-created_at")),
            models.Index(fields=("target", "-created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} {self.target}"

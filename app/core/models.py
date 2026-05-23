"""Cross-cutting application settings stored in the DB.

The fields here have matching env-var overrides in `config.settings`. The
resolver functions in `core.services` consult env first; if the env value
is set and non-empty, it wins and the corresponding UI field is rendered
read-only with a "locked by env" badge. This lets operators choose where
to authoritatively configure: edit-in-place via the UI, or pin from
Ansible-rendered .env in production.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class AppSetting(models.Model):
    """Singleton row. Use AppSetting.get() rather than calling .objects."""

    admin_group_name = models.CharField(
        _("admin group name"),
        max_length=255,
        default="steward-admins",
        help_text=_(
            "Name of the Authentik group whose members are admitted into "
            "Steward. Must match a real group in Authentik."
        ),
    )
    invite_flow_slug = models.CharField(
        _("invite flow slug"),
        max_length=255,
        blank=True,
        default="",
        help_text=_(
            "Slug of an Authentik enrollment flow attached to invitations "
            "for new members. Leave blank to skip invitation creation."
        ),
    )
    group_filter_regex = models.CharField(
        _("group filter regex"),
        max_length=500,
        blank=True,
        default="",
        help_text=_(
            "Regex matched (via re.search) against Authentik group names. "
            "Only matching groups appear in Steward's UI. Empty shows all "
            "groups. Example: ^(union|committee)-"
        ),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("application settings")
        verbose_name_plural = _("application settings")

    def __str__(self) -> str:
        return "Steward settings"

    def save(self, *args, **kwargs):
        # Enforce singleton: every save lands on pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("AppSetting is a singleton and cannot be deleted."))

    @classmethod
    def get(cls) -> "AppSetting":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

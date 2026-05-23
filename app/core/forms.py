import re

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import AppSetting


class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ("admin_group_name", "invite_flow_slug", "group_filter_regex")
        labels = {
            "admin_group_name": _("Admin group name"),
            "invite_flow_slug": _("Invitation flow slug"),
            "group_filter_regex": _("Group filter regex"),
        }

    def clean_group_filter_regex(self):
        value = (self.cleaned_data.get("group_filter_regex") or "").strip()
        if not value:
            return ""
        try:
            re.compile(value)
        except re.error as e:
            raise forms.ValidationError(
                _("Invalid regular expression: %(err)s") % {"err": e}
            ) from e
        return value

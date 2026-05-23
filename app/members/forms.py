from django import forms
from django.utils.translation import gettext_lazy as _


class MemberForm(forms.Form):
    name = forms.CharField(max_length=255, label=_("Full name"))
    email = forms.EmailField(label=_("Email (used as login)"))
    x_number = forms.CharField(
        max_length=64,
        required=False,
        label=_("X-Number"),
        help_text=_("Membership number. Optional."),
    )


class AddGroupForm(forms.Form):
    group_uuid = forms.CharField(widget=forms.HiddenInput)


class RemoveGroupForm(forms.Form):
    group_uuid = forms.CharField(widget=forms.HiddenInput)


class RemoveMFAForm(forms.Form):
    device_type = forms.CharField(widget=forms.HiddenInput)
    device_pk = forms.CharField(widget=forms.HiddenInput)
    device_name = forms.CharField(widget=forms.HiddenInput, required=False)

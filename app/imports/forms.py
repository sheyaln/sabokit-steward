from django import forms
from django.utils.translation import gettext_lazy as _


class UploadForm(forms.Form):
    csv = forms.FileField(
        label=_("CSV file"),
        help_text=_("Columns: email, name, x_number (x_number optional)."),
    )

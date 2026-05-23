from audit.models import AuditLog
from audit.services import record
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from .forms import AppSettingForm
from .models import AppSetting
from .services import (
    admin_group_locked,
    admin_group_name,
    group_filter_locked,
    group_filter_regex,
    invite_flow_locked,
    invite_flow_slug,
)


def healthz(_request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")


@login_required
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "core/index.html", {"user": request.user})


def access_denied(request: HttpRequest) -> HttpResponse:
    """Landing page after a rejected OIDC login. Never login-required (would
    cause the redirect loop this exists to break)."""
    return render(
        request,
        "core/access_denied.html",
        {"admin_group": admin_group_name()},
        status=403,
    )


def logged_out(request: HttpRequest) -> HttpResponse:
    """Post-logout landing page. Never login-required -- visiting it must
    NOT bounce through OIDC, otherwise SSO immediately re-authenticates
    the user and logout looks like a no-op."""
    return render(request, "core/logged_out.html")


EDITABLE_SETTINGS = ("admin_group_name", "invite_flow_slug", "group_filter_regex")


@login_required
def app_settings(request: HttpRequest) -> HttpResponse:
    instance = AppSetting.get()
    locked = {
        "admin_group_name": admin_group_locked(),
        "invite_flow_slug": invite_flow_locked(),
        "group_filter_regex": group_filter_locked(),
    }
    if request.method == "POST":
        form = AppSettingForm(request.POST, instance=instance)
        if form.is_valid():
            before = {field: getattr(instance, field) for field in EDITABLE_SETTINGS}
            # Don't persist fields that are locked by env -- the env value
            # is shadowing the DB value anyway, so writing the form's input
            # would be misleading silent state. Surface a notice instead.
            ignored = []
            for field in EDITABLE_SETTINGS:
                if locked[field]:
                    setattr(form.instance, field, getattr(instance, field))
                    ignored.append(field)
            form.save()
            after = {field: getattr(form.instance, field) for field in EDITABLE_SETTINGS}
            if before != after:
                record(
                    actor=request.user,
                    action=AuditLog.Action.SETTINGS_UPDATE,
                    target="app-settings",
                    before=before,
                    after=after,
                )
            if ignored:
                messages.warning(
                    request,
                    _("Saved. Ignored env-locked fields: %(fields)s.")
                    % {"fields": ", ".join(ignored)},
                )
            else:
                messages.success(request, _("Settings saved."))
            return redirect(reverse("settings"))
    else:
        form = AppSettingForm(instance=instance)
    for field, is_locked in locked.items():
        if is_locked:
            form.fields[field].disabled = True
    return render(
        request,
        "core/settings.html",
        {
            "form": form,
            "locked": locked,
            "effective_admin_group": admin_group_name(),
            "effective_invite_flow": invite_flow_slug(),
            "effective_group_filter": group_filter_regex(),
        },
    )

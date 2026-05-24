from __future__ import annotations

import logging

from core.authentik import AuthentikError
from core.services import filter_groups
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import services
from .forms import AddGroupForm, MemberForm, RemoveGroupForm, RemoveMFAForm

logger = logging.getLogger(__name__)


def _client():
    return services.client()


@login_required
def member_list(request: HttpRequest) -> HttpResponse:
    search = request.GET.get("q", "").strip() or None
    group = request.GET.get("group") or None
    state = request.GET.get("state") or ""
    is_active = {"active": True, "inactive": False}.get(state)
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    ak = _client()
    try:
        data = ak.list_users(search=search, group=group, is_active=is_active, page=page)
        groups = filter_groups(ak.list_all_groups())
    except AuthentikError as e:
        messages.error(request, _("Authentik API error: %(err)s") % {"err": e})
        data = {"results": [], "pagination": {}}
        groups = []
    return render(
        request,
        "members/list.html",
        {
            "members": data.get("results", []),
            "pagination": data.get("pagination") or {},
            "groups": groups,
            "filters": {"q": search or "", "group": group or "", "state": state},
        },
    )


@login_required
def member_create(request: HttpRequest) -> HttpResponse:
    form = MemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user, invitation = services.create_member(
                actor=request.user,
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                x_number=form.cleaned_data["x_number"],
            )
        except AuthentikError as e:
            messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
        else:
            msg = _("Created %(email)s.") % {"email": user["email"]}
            if invitation:
                url = invitation.get("enrollment_url") or ""
                if url:
                    msg += " " + _("Invitation URL: %(url)s") % {"url": url}
                else:
                    # Fallback when we couldn't derive a browser-facing
                    # Authentik base (e.g. OIDC_OP_AUTHORIZATION_ENDPOINT
                    # unset) -- still useful for the admin to know an
                    # invitation exists in Authentik.
                    msg += " " + _("Invitation pk=%(pk)s.") % {"pk": invitation.get("pk")}
            messages.success(request, msg)
            return redirect(reverse("members:detail", args=[user["pk"]]))
    return render(request, "members/form.html", {"form": form, "action": _("Create")})


@login_required
def member_detail(request: HttpRequest, pk: int) -> HttpResponse:
    ak = _client()
    try:
        user = ak.get_user(pk)
        all_groups = ak.list_all_groups()
    except AuthentikError as e:
        messages.error(request, _("Authentik error: %(err)s") % {"err": e})
        return redirect("members:list")
    try:
        mfa_devices = services.list_mfa_devices(user_pk=pk)
    except AuthentikError as e:
        messages.warning(request, _("Could not load MFA devices: %(err)s") % {"err": e})
        mfa_devices = []
    visible_groups = filter_groups(all_groups)
    member_group_uuids = set(user.get("groups") or [])
    # `in_groups` is computed from all_groups, NOT visible_groups, so that a
    # member who already belongs to a group hidden by the filter still sees
    # it (otherwise the UI silently lies about their state).
    in_groups = [g for g in all_groups if g["pk"] in member_group_uuids]
    available_groups = [g for g in visible_groups if g["pk"] not in member_group_uuids]
    return render(
        request,
        "members/detail.html",
        {
            "member": user,
            "in_groups": in_groups,
            "available_groups": available_groups,
            "mfa_devices": mfa_devices,
            "x_number": (user.get("attributes") or {}).get("x_number", ""),
            "add_form": AddGroupForm(),
            "remove_form": RemoveGroupForm(),
        },
    )


@login_required
def member_edit(request: HttpRequest, pk: int) -> HttpResponse:
    ak = _client()
    try:
        user = ak.get_user(pk)
    except AuthentikError as e:
        messages.error(request, _("Authentik error: %(err)s") % {"err": e})
        return redirect("members:list")
    initial = {
        "name": user.get("name"),
        "email": user.get("email"),
        "x_number": (user.get("attributes") or {}).get("x_number", ""),
    }
    form = MemberForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_member(
                actor=request.user,
                pk=pk,
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                x_number=form.cleaned_data["x_number"],
            )
        except AuthentikError as e:
            messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
        else:
            messages.success(request, _("Updated."))
            return redirect(reverse("members:detail", args=[pk]))
    return render(request, "members/form.html", {"form": form, "action": _("Save")})


@login_required
@require_POST
def member_activate(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active(request, pk, True)


@login_required
@require_POST
def member_deactivate(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active(request, pk, False)


def _toggle_active(request: HttpRequest, pk: int, active: bool) -> HttpResponse:
    try:
        services.set_active(actor=request.user, pk=pk, active=active)
    except AuthentikError as e:
        messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
    else:
        if active:
            messages.success(request, _("Member activated."))
        else:
            messages.success(request, _("Member deactivated."))
    return redirect(reverse("members:detail", args=[pk]))


@login_required
@require_POST
def member_add_group(request: HttpRequest, pk: int) -> HttpResponse:
    form = AddGroupForm(request.POST)
    if form.is_valid():
        try:
            ak = _client()
            user = ak.get_user(pk)
            group = next(
                (g for g in ak.list_all_groups() if g["pk"] == form.cleaned_data["group_uuid"]),
                None,
            )
            if group is None:
                messages.error(request, _("Group not found."))
            else:
                services.add_to_group(
                    actor=request.user,
                    user_pk=pk,
                    group_uuid=group["pk"],
                    group_name=group["name"],
                    target=user.get("email") or user.get("username"),
                )
                messages.success(request, _("Added to %(group)s.") % {"group": group["name"]})
        except AuthentikError as e:
            messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
    return redirect(reverse("members:detail", args=[pk]))


@login_required
@require_POST
def member_password_reset(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        services.send_password_reset(actor=request.user, pk=pk)
    except AuthentikError as e:
        messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
    else:
        messages.success(request, _("Password reset email sent."))
    return redirect(reverse("members:detail", args=[pk]))


@login_required
@require_POST
def member_remove_mfa(request: HttpRequest, pk: int) -> HttpResponse:
    form = RemoveMFAForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Invalid MFA device reference."))
        return redirect(reverse("members:detail", args=[pk]))
    try:
        ak = _client()
        user = ak.get_user(pk)
        services.remove_mfa_device(
            actor=request.user,
            user_pk=pk,
            device_type=form.cleaned_data["device_type"],
            device_pk=form.cleaned_data["device_pk"],
            device_name=form.cleaned_data.get("device_name") or "",
            target=user.get("email") or user.get("username") or str(pk),
        )
    except AuthentikError as e:
        messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
    else:
        messages.success(request, _("MFA device removed."))
    return redirect(reverse("members:detail", args=[pk]))


@login_required
@require_POST
def member_remove_group(request: HttpRequest, pk: int) -> HttpResponse:
    form = RemoveGroupForm(request.POST)
    if form.is_valid():
        try:
            ak = _client()
            user = ak.get_user(pk)
            group = next(
                (g for g in ak.list_all_groups() if g["pk"] == form.cleaned_data["group_uuid"]),
                None,
            )
            if group is None:
                messages.error(request, _("Group not found."))
            else:
                services.remove_from_group(
                    actor=request.user,
                    user_pk=pk,
                    group_uuid=group["pk"],
                    group_name=group["name"],
                    target=user.get("email") or user.get("username"),
                )
                messages.success(request, _("Removed from %(group)s.") % {"group": group["name"]})
        except AuthentikError as e:
            messages.error(request, _("Authentik refused: %(err)s") % {"err": e.payload or e})
    return redirect(reverse("members:detail", args=[pk]))

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import AuditLog


@login_required
def audit_list(request: HttpRequest) -> HttpResponse:
    qs = AuditLog.objects.select_related("actor").all()
    action = request.GET.get("action") or ""
    target = request.GET.get("target") or ""
    actor = request.GET.get("actor") or ""
    if action:
        qs = qs.filter(action=action)
    if target:
        qs = qs.filter(target__icontains=target)
    if actor:
        qs = qs.filter(actor_username__icontains=actor)
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "audit/list.html",
        {
            "page": page,
            "actions": AuditLog.Action.choices,
            "filters": {"action": action, "target": target, "actor": actor},
        },
    )

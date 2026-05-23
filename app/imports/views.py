from __future__ import annotations

import logging

from audit.models import AuditLog
from audit.services import record
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_q.tasks import async_task

from . import services
from .forms import UploadForm
from .models import ImportJob

logger = logging.getLogger(__name__)


@login_required
def import_list(request: HttpRequest) -> HttpResponse:
    jobs = ImportJob.objects.select_related("uploaded_by").all()[:50]
    return render(request, "imports/list.html", {"jobs": jobs})


@login_required
def import_create(request: HttpRequest) -> HttpResponse:
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded = request.FILES["csv"]
        job = ImportJob.objects.create(
            uploaded_by=request.user,
            original_filename=uploaded.name,
        )
        job.csv.save(uploaded.name, ContentFile(uploaded.read()), save=True)
        record(
            actor=request.user,
            action=AuditLog.Action.IMPORT_CREATE,
            target=uploaded.name,
            note=f"job pk={job.pk}",
        )
        try:
            services.dry_run(job)
        except Exception as e:  # noqa: BLE001
            logger.exception("dry-run failed for job %s", job.pk)
            job.status = ImportJob.Status.FAILED
            job.summary = {"fatal": str(e)}
            job.save(update_fields=("status", "summary"))
            messages.error(request, _("Could not parse CSV: %(err)s") % {"err": e})
            return redirect(reverse("imports:detail", args=[job.pk]))
        messages.success(request, _("CSV parsed. Review below, then apply."))
        return redirect(reverse("imports:detail", args=[job.pk]))
    return render(request, "imports/form.html", {"form": form})


@login_required
def import_detail(request: HttpRequest, pk: int) -> HttpResponse:
    job = get_object_or_404(ImportJob, pk=pk)
    rows = job.rows.all()
    return render(request, "imports/detail.html", {"job": job, "rows": rows})


@login_required
@require_POST
def import_apply(request: HttpRequest, pk: int) -> HttpResponse:
    job = get_object_or_404(ImportJob, pk=pk)
    if job.status not in (ImportJob.Status.PREVIEW, ImportJob.Status.FAILED):
        messages.error(
            request,
            _("Cannot apply: job is in %(status)s state.") % {"status": job.status},
        )
        return redirect(reverse("imports:detail", args=[pk]))
    job.status = ImportJob.Status.RUNNING
    job.save(update_fields=("status",))
    async_task("imports.tasks.apply_import", job.pk)
    messages.success(request, _("Job enqueued. Refresh to see progress."))
    return redirect(reverse("imports:detail", args=[pk]))

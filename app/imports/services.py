"""CSV import: dry-run preview + idempotent apply.

Idempotency is keyed on email -- if an Authentik user already exists with the
row's email, the row is treated as an `update`; otherwise it's a `create`.
Empty `email` rows are skipped with an error message rather than aborting the
whole job.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable

from audit.models import AuditLog
from audit.services import record
from core.authentik import AuthentikClient, AuthentikError
from django.utils import timezone

from .models import ImportJob, ImportJobRow

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = {"email", "name"}
OPTIONAL_HEADERS = {"x_number"}


def _read_rows(csv_bytes: bytes) -> Iterable[dict[str, str]]:
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV is empty.")
    headers = {h.strip() for h in reader.fieldnames}
    missing = REQUIRED_HEADERS - headers
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    for raw in reader:
        yield {k: (v or "").strip() for k, v in raw.items() if k}


def dry_run(job: ImportJob) -> None:
    """Read the CSV, classify each row, store ImportJobRow placeholders."""
    job.rows.all().delete()
    ak = AuthentikClient()
    job.csv.open("rb")
    try:
        rows = list(_read_rows(job.csv.read()))
    finally:
        job.csv.close()
    counts = {"create": 0, "update": 0, "skip": 0, "error": 0}
    for idx, row in enumerate(rows, start=2):  # row 1 is the header
        email = row.get("email", "")
        name = row.get("name", "")
        x_number = row.get("x_number", "")
        if not email:
            ImportJobRow.objects.create(
                job=job,
                row_number=idx,
                email="",
                name=name,
                x_number=x_number,
                action=ImportJobRow.Action.ERROR,
                message="Missing email.",
            )
            counts["error"] += 1
            continue
        try:
            existing = ak.find_user_by_email(email)
        except AuthentikError as e:
            ImportJobRow.objects.create(
                job=job,
                row_number=idx,
                email=email,
                name=name,
                x_number=x_number,
                action=ImportJobRow.Action.ERROR,
                message=f"Authentik error: {e}",
            )
            counts["error"] += 1
            continue
        if existing:
            ImportJobRow.objects.create(
                job=job,
                row_number=idx,
                email=email,
                name=name,
                x_number=x_number,
                action=ImportJobRow.Action.UPDATE,
                authentik_pk=existing.get("pk"),
                message="Will update existing user.",
            )
            counts["update"] += 1
        else:
            ImportJobRow.objects.create(
                job=job,
                row_number=idx,
                email=email,
                name=name,
                x_number=x_number,
                action=ImportJobRow.Action.CREATE,
                message="Will create new user.",
            )
            counts["create"] += 1
    job.status = ImportJob.Status.PREVIEW
    job.summary = {"counts": counts, "total": len(rows)}
    job.save(update_fields=("status", "summary"))


def run_apply(job_id: int) -> None:
    """Apply each non-error row idempotently. Called by Django-Q worker."""
    job = ImportJob.objects.get(pk=job_id)
    job.status = ImportJob.Status.RUNNING
    job.save(update_fields=("status",))
    record(
        actor=job.uploaded_by,
        action=AuditLog.Action.IMPORT_RUN,
        target=job.original_filename,
        note=f"job pk={job.pk} starting",
    )
    ak = AuthentikClient()
    counts = {"create": 0, "update": 0, "skip": 0, "error": 0}
    try:
        for row in job.rows.all():
            if row.action == ImportJobRow.Action.ERROR:
                counts["error"] += 1
                continue
            try:
                _apply_row(ak, row, actor=job.uploaded_by)
                counts[row.action] += 1
            except AuthentikError as e:
                row.action = ImportJobRow.Action.ERROR
                row.message = f"Apply failed: {e.payload or e}"
                row.applied = False
                row.save(update_fields=("action", "message", "applied"))
                counts["error"] += 1
    except Exception as e:  # noqa: BLE001
        logger.exception("Bulk import job %s crashed", job.pk)
        job.status = ImportJob.Status.FAILED
        job.summary = {**job.summary, "fatal": str(e), "counts": counts}
        job.completed_at = timezone.now()
        job.save(update_fields=("status", "summary", "completed_at"))
        return
    job.status = ImportJob.Status.COMPLETED
    job.summary = {**job.summary, "counts": counts}
    job.completed_at = timezone.now()
    job.save(update_fields=("status", "summary", "completed_at"))


def _apply_row(ak: AuthentikClient, row: ImportJobRow, *, actor) -> None:
    attrs = {"x_number": row.x_number} if row.x_number else {}
    if row.action == ImportJobRow.Action.CREATE:
        user = ak.create_user(
            username=row.email,
            name=row.name,
            email=row.email,
            attributes=attrs,
            is_active=True,
        )
        row.authentik_pk = user["pk"]
        row.applied = True
        row.message = "Created."
        row.save(update_fields=("authentik_pk", "applied", "message"))
        record(
            actor=actor,
            action=AuditLog.Action.MEMBER_CREATE,
            target=row.email,
            after={
                "pk": user.get("pk"),
                "email": user.get("email"),
                "name": user.get("name"),
            },
            note=f"bulk import job pk={row.job_id}",
        )
    elif row.action == ImportJobRow.Action.UPDATE:
        before = ak.get_user(row.authentik_pk)
        merged_attrs = dict(before.get("attributes") or {})
        if row.x_number:
            merged_attrs["x_number"] = row.x_number
        updated = ak.update_user(
            row.authentik_pk,
            name=row.name,
            attributes=merged_attrs,
        )
        row.applied = True
        row.message = "Updated."
        row.save(update_fields=("applied", "message"))
        record(
            actor=actor,
            action=AuditLog.Action.MEMBER_UPDATE,
            target=row.email,
            before={"name": before.get("name"), "attributes": before.get("attributes")},
            after={"name": updated.get("name"), "attributes": updated.get("attributes")},
            note=f"bulk import job pk={row.job_id}",
        )

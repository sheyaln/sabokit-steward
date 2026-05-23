"""Django-Q entry point. Kept thin so the heavy lifting stays testable."""

from .services import run_apply


def apply_import(job_id: int) -> None:
    run_apply(job_id)

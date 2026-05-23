from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from .models import AuditLog


def record(
    *,
    actor: AbstractBaseUser | AnonymousUser | None,
    action: str,
    target: str = "",
    before: Any = None,
    after: Any = None,
    note: str = "",
) -> AuditLog:
    """Persist an audit event. Call this for every mutating Authentik API call."""
    actor_is_real = actor is not None and getattr(actor, "is_authenticated", False)
    return AuditLog.objects.create(
        actor=actor if actor_is_real else None,
        actor_username=getattr(actor, "username", "") if actor_is_real else "",
        action=action,
        target=target or "",
        before=_safe(before),
        after=_safe(after),
        note=note or "",
    )


def _safe(value: Any) -> Any:
    """Pre-filter to keep the JSON small and avoid leaking large blobs."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: value[k] for k in value if k not in {"password", "raw_password"}}
    return value

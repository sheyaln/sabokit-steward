"""Member operations: thin orchestration over the Authentik API + audit log.

Every mutation hits the Authentik API and writes an `AuditLog` row in the same
call. Read-only operations skip the audit log.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from audit.models import AuditLog
from audit.services import record
from core.authentik import AuthentikClient, AuthentikError
from core.services import invite_flow_slug
from django.conf import settings

logger = logging.getLogger(__name__)


def client() -> AuthentikClient:
    return AuthentikClient()


def _snapshot(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "pk": user.get("pk"),
        "username": user.get("username"),
        "name": user.get("name"),
        "email": user.get("email"),
        "is_active": user.get("is_active"),
        "attributes": user.get("attributes") or {},
        "groups": user.get("groups") or [],
    }


def create_member(
    *,
    actor,
    name: str,
    email: str,
    x_number: str = "",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Create a user in Authentik. Returns (user, invitation_or_none)."""
    ak = client()
    attrs: dict[str, Any] = {}
    if x_number:
        attrs["x_number"] = x_number
    user = ak.create_user(
        username=email,
        name=name,
        email=email,
        attributes=attrs,
        groups=[],
        is_active=True,
    )
    record(
        actor=actor,
        action=AuditLog.Action.MEMBER_CREATE,
        target=email,
        after=_snapshot(user),
    )
    invitation = _maybe_invite(actor=actor, user=user)
    return user, invitation


def update_member(
    *,
    actor,
    pk: int,
    name: str,
    email: str,
    x_number: str = "",
) -> dict[str, Any]:
    ak = client()
    before = ak.get_user(pk)
    attrs = dict(before.get("attributes") or {})
    if x_number:
        attrs["x_number"] = x_number
    else:
        attrs.pop("x_number", None)
    updated = ak.update_user(
        pk,
        username=email,
        name=name,
        email=email,
        attributes=attrs,
    )
    record(
        actor=actor,
        action=AuditLog.Action.MEMBER_UPDATE,
        target=email,
        before=_snapshot(before),
        after=_snapshot(updated),
    )
    return updated


def set_active(*, actor, pk: int, active: bool) -> dict[str, Any]:
    ak = client()
    before = ak.get_user(pk)
    updated = ak.set_user_active(pk, active)
    record(
        actor=actor,
        action=(AuditLog.Action.MEMBER_ACTIVATE if active else AuditLog.Action.MEMBER_DEACTIVATE),
        target=before.get("email") or before.get("username") or str(pk),
        before={"is_active": before.get("is_active")},
        after={"is_active": updated.get("is_active")},
    )
    return updated


def send_password_reset(*, actor, pk: int) -> dict[str, Any]:
    ak = client()
    user = ak.get_user(pk)
    ak.send_recovery_email(pk)
    record(
        actor=actor,
        action=AuditLog.Action.MEMBER_PASSWORD_RESET,
        target=user.get("email") or user.get("username") or str(pk),
    )
    return user


def list_mfa_devices(*, user_pk: int) -> list[dict[str, Any]]:
    return client().list_user_mfa_devices(user_pk)


def remove_mfa_device(
    *,
    actor,
    user_pk: int,
    device_type: str,
    device_pk: str,
    device_name: str,
    target: str,
) -> None:
    client().delete_mfa_device(device_type, device_pk)
    record(
        actor=actor,
        action=AuditLog.Action.MEMBER_MFA_REMOVE,
        target=target,
        before={
            "device_type": device_type,
            "device_pk": device_pk,
            "device_name": device_name,
        },
    )


def add_to_group(*, actor, user_pk: int, group_uuid: str, group_name: str, target: str) -> None:
    client().add_user_to_group(group_uuid, user_pk)
    record(
        actor=actor,
        action=AuditLog.Action.GROUP_ADD,
        target=target,
        after={"group": group_name, "group_uuid": group_uuid},
    )


def remove_from_group(
    *, actor, user_pk: int, group_uuid: str, group_name: str, target: str
) -> None:
    client().remove_user_from_group(group_uuid, user_pk)
    record(
        actor=actor,
        action=AuditLog.Action.GROUP_REMOVE,
        target=target,
        before={"group": group_name, "group_uuid": group_uuid},
    )


def _maybe_invite(*, actor, user: dict[str, Any]) -> dict[str, Any] | None:
    """Create an Authentik invitation linked to the configured enrollment flow.

    The returned dict carries the invitation primary key plus a precomputed
    `enrollment_url` the admin can share. Authentik itself only emails the
    invitee when the configured flow has an email stage -- this URL gives
    admins a fallback they can paste into any other channel.
    """
    flow_slug = invite_flow_slug()
    if not flow_slug:
        return None
    ak = client()
    try:
        flow = ak.find_flow_by_slug(flow_slug)
        if not flow:
            logger.warning("AUTHENTIK_INVITE_FLOW=%s not found in Authentik", flow_slug)
            return None
        invitation = ak.create_invitation(
            name=f"steward-invite-{user['username']}",
            flow_pk=flow["pk"],
            fixed_data={
                "username": user["username"],
                "email": user["email"],
                "name": user["name"],
            },
            single_use=True,
        )
        invitation["enrollment_url"] = _enrollment_url(flow_slug, invitation.get("pk"))
        record(
            actor=actor,
            action=AuditLog.Action.MEMBER_CREATE,
            target=user["email"],
            after={
                "invitation_pk": invitation.get("pk"),
                "enrollment_url": invitation["enrollment_url"],
            },
            note="invitation created",
        )
        return invitation
    except AuthentikError:
        logger.exception("Failed to create Authentik invitation for %s", user.get("email"))
        return None


def _enrollment_url(flow_slug: str, invitation_pk: Any) -> str:
    """Construct the user-facing URL that consumes the invitation token.

    Derived from OIDC_OP_AUTHORIZATION_ENDPOINT (which is browser-facing,
    unlike AUTHENTIK_API_URL which is typically an in-cluster hostname).
    Returns "" when we can't derive a base.
    """
    if not invitation_pk:
        return ""
    auth_ep = getattr(settings, "OIDC_OP_AUTHORIZATION_ENDPOINT", "") or ""
    if not auth_ep:
        return ""
    parts = urlsplit(auth_ep)
    if not parts.scheme or not parts.netloc:
        return ""
    base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    return f"{base}/if/flow/{flow_slug}/?itoken={invitation_pk}"

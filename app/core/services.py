"""Settings resolver.

For each piece of cross-cutting configuration, the env var (if set + non-empty)
wins and the DB field is shadowed; otherwise the DB field is the source of
truth. Code that needs these values should call the resolver, never read
`django.conf.settings.AUTHENTIK_*` directly.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from django.conf import settings

from .models import AppSetting

logger = logging.getLogger(__name__)


def admin_group_name() -> str:
    """The Authentik group required for Steward access."""
    return settings.AUTHENTIK_ADMIN_GROUP or AppSetting.get().admin_group_name


def admin_group_locked() -> bool:
    return bool(settings.AUTHENTIK_ADMIN_GROUP)


def invite_flow_slug() -> str:
    """Slug of the Authentik enrollment flow for new-member invitations."""
    return settings.AUTHENTIK_INVITE_FLOW or AppSetting.get().invite_flow_slug


def invite_flow_locked() -> bool:
    return bool(settings.AUTHENTIK_INVITE_FLOW)


def group_filter_regex() -> str:
    """Regex restricting which Authentik groups appear in the Steward UI."""
    return settings.AUTHENTIK_GROUP_FILTER or AppSetting.get().group_filter_regex


def group_filter_locked() -> bool:
    return bool(settings.AUTHENTIK_GROUP_FILTER)


def filter_groups(groups: Iterable[dict]) -> list[dict]:
    """Drop Authentik group dicts whose `name` doesn't match the configured
    regex. Returns groups unchanged when the filter is empty or invalid --
    a malformed regex is logged once and then ignored so a bad UI input
    can't lock admins out of group assignment entirely."""
    pattern = group_filter_regex()
    if not pattern:
        return list(groups)
    try:
        rx = re.compile(pattern)
    except re.error as e:
        logger.warning("Ignoring invalid AUTHENTIK_GROUP_FILTER regex %r: %s", pattern, e)
        return list(groups)
    return [g for g in groups if rx.search(g.get("name") or "")]

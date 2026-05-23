"""OIDC backend: gate Steward access on Authentik group membership."""

from __future__ import annotations

import logging
from typing import Any

from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .services import admin_group_name

logger = logging.getLogger(__name__)


class StewardOIDCBackend(OIDCAuthenticationBackend):
    """Require membership in the configured admin group; flag is_staff for it."""

    def _groups_from_claims(self, claims: dict[str, Any]) -> list[str]:
        groups = claims.get("groups") or []
        return [str(g) for g in groups]

    def _is_admin(self, claims: dict[str, Any]) -> bool:
        return admin_group_name() in self._groups_from_claims(claims)

    def verify_claims(self, claims: dict[str, Any]) -> bool:
        if not super().verify_claims(claims):
            return False
        if not self._is_admin(claims):
            logger.warning(
                "Rejecting OIDC login for %s: missing required group %s",
                claims.get("email") or claims.get("preferred_username"),
                admin_group_name(),
            )
            return False
        return True

    def _apply_claims(self, user, claims: dict[str, Any]) -> None:
        user.is_staff = self._is_admin(claims)
        user.is_superuser = False
        # given_name is the canonical OIDC first-name claim, but many IdPs
        # (Authentik included, by default) don't populate it -- they send
        # only the joined `name` claim. Fall back to the first token of
        # that so we have something better than an opaque sub for display.
        first = (claims.get("given_name") or "").strip()
        last = (claims.get("family_name") or "").strip()
        if not first:
            full = (claims.get("name") or "").strip()
            if full:
                parts = full.split()
                first = parts[0]
                if not last and len(parts) > 1:
                    last = " ".join(parts[1:])
        if first:
            user.first_name = first
        if last:
            user.last_name = last
        if claims.get("email"):
            user.email = claims["email"]

    def create_user(self, claims: dict[str, Any]):
        user = super().create_user(claims)
        self._apply_claims(user, claims)
        user.save()
        return user

    def update_user(self, user, claims: dict[str, Any]):
        self._apply_claims(user, claims)
        user.save()
        return user

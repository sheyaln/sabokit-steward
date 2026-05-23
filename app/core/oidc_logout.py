"""Constructs the URL `mozilla-django-oidc` redirects to AFTER clearing
the Django session, so we can terminate the Authentik session in the same
flow. Without this hook, the user's Steward session is cleared but
Authentik's SSO cookie keeps them signed in -- the next login_required
silently reauthenticates them and logout looks like a no-op.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse


def authentik_end_session(request) -> str:
    """Return Authentik's RP-initiated logout URL.

    Falls back to the local /logged-out/ page if the end-session endpoint
    isn't configured -- the page tells the user they may still be signed
    in to Authentik and offers a manual sign-out link.
    """
    local_after = request.build_absolute_uri(reverse("logged_out"))
    end_session = getattr(settings, "OIDC_OP_END_SESSION_ENDPOINT", "") or ""
    if not end_session:
        return local_after
    params = {"post_logout_redirect_uri": local_after}
    id_token = request.session.get("oidc_id_token")
    if id_token:
        params["id_token_hint"] = id_token
    return f"{end_session}?{urlencode(params)}"

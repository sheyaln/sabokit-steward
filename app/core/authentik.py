"""Thin wrapper around the Authentik REST API.

Steward is the source of truth for *audit history*; Authentik is the source of
truth for *member state*. This module deliberately does not cache, mirror, or
normalize Authentik responses -- callers get the raw JSON dicts back.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings


class AuthentikError(RuntimeError):
    """Raised when the Authentik API returns a non-2xx response."""

    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AuthentikClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (base_url or settings.AUTHENTIK_API_URL).rstrip("/") + "/"
        self.token = token or settings.AUTHENTIK_API_TOKEN
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._session.request(method, self._url(path), timeout=self.timeout, **kwargs)
        if resp.status_code == 204 or not resp.content:
            body = None
        else:
            try:
                body = resp.json()
            except ValueError:
                body = resp.text
        if resp.status_code >= 400:
            raise AuthentikError(
                f"Authentik {method} {path} -> {resp.status_code}",
                status_code=resp.status_code,
                payload=body,
            )
        return body

    def list_users(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
        group: str | None = None,
        is_active: bool | None = None,
        path_startswith: str | None = "users",
    ) -> dict[str, Any]:
        """Paginated user list. `group` filters by group UUID."""
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        if group:
            params["groups_by_pk"] = group
        if is_active is not None:
            params["is_active"] = "true" if is_active else "false"
        if path_startswith:
            params["path_startswith"] = path_startswith
        return self._request("GET", "api/v3/core/users/", params=params)

    def get_user(self, pk: int) -> dict[str, Any]:
        return self._request("GET", f"api/v3/core/users/{pk}/")

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        data = self._request("GET", "api/v3/core/users/", params={"email": email})
        results = data.get("results") or []
        return results[0] if results else None

    def create_user(
        self,
        *,
        username: str,
        name: str,
        email: str,
        attributes: dict[str, Any] | None = None,
        groups: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        body = {
            "username": username,
            "name": name,
            "email": email,
            "is_active": is_active,
            "path": "users",
            "attributes": attributes or {},
            "groups": groups or [],
        }
        return self._request("POST", "api/v3/core/users/", json=body)

    def update_user(self, pk: int, **fields: Any) -> dict[str, Any]:
        return self._request("PATCH", f"api/v3/core/users/{pk}/", json=fields)

    def set_user_active(self, pk: int, active: bool) -> dict[str, Any]:
        return self.update_user(pk, is_active=active)

    def send_recovery_email(self, pk: int) -> None:
        """Trigger Authentik to send a recovery (password reset) email."""
        self._request("POST", f"api/v3/core/users/{pk}/recovery_email/")

    # Authentik exposes one admin endpoint per device type. `all/` returns a
    # combined list with a `type` field naming which endpoint owns each device.
    MFA_DEVICE_TYPES: tuple[str, ...] = (
        "totp",
        "webauthn",
        "static",
        "duo",
        "sms",
        "email",
    )

    def list_user_mfa_devices(self, user_pk: int) -> list[dict[str, Any]]:
        data = self._request("GET", "api/v3/authenticators/admin/all/", params={"user": user_pk})
        if isinstance(data, list):
            return data
        return data.get("results") or []

    def delete_mfa_device(self, device_type: str, device_pk: str | int) -> None:
        if device_type not in self.MFA_DEVICE_TYPES:
            raise AuthentikError(f"Unsupported MFA device type: {device_type}")
        self._request("DELETE", f"api/v3/authenticators/admin/{device_type}/{device_pk}/")

    def list_groups(self, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self._request(
            "GET", "api/v3/core/groups/", params={"page": page, "page_size": page_size}
        )

    # Hard cap to avoid pathological cases (misconfigured Authentik returning
    # tens of thousands of groups). The UI is unusable past a few hundred
    # entries anyway -- callers should narrow with `group_filter_regex`.
    LIST_ALL_GROUPS_MAX_PAGES = 50

    def list_all_groups(self, *, page_size: int = 100) -> list[dict[str, Any]]:
        """Aggregate all pages of `list_groups`. The single-page method
        misses anything past the first 100, which silently breaks
        `group_filter_regex` whenever an Authentik instance has more
        groups than fit on one page."""
        out: list[dict[str, Any]] = []
        for page in range(1, self.LIST_ALL_GROUPS_MAX_PAGES + 1):
            data = self.list_groups(page=page, page_size=page_size)
            out.extend(data.get("results") or [])
            pagination = data.get("pagination") or {}
            if not pagination.get("next"):
                break
        return out

    def find_group_by_name(self, name: str) -> dict[str, Any] | None:
        data = self._request("GET", "api/v3/core/groups/", params={"name": name})
        results = data.get("results") or []
        return results[0] if results else None

    def add_user_to_group(self, group_uuid: str, user_pk: int) -> None:
        self._request("POST", f"api/v3/core/groups/{group_uuid}/add_user/", json={"pk": user_pk})

    def remove_user_from_group(self, group_uuid: str, user_pk: int) -> None:
        self._request("POST", f"api/v3/core/groups/{group_uuid}/remove_user/", json={"pk": user_pk})

    def find_flow_by_slug(self, slug: str) -> dict[str, Any] | None:
        data = self._request("GET", "api/v3/flows/instances/", params={"slug": slug})
        results = data.get("results") or []
        return results[0] if results else None

    def create_invitation(
        self,
        *,
        name: str,
        flow_pk: str,
        fixed_data: dict[str, Any] | None = None,
        single_use: bool = True,
    ) -> dict[str, Any]:
        body = {
            "name": name,
            "flow": flow_pk,
            "fixed_data": fixed_data or {},
            "single_use": single_use,
        }
        return self._request("POST", "api/v3/stages/invitation/invitations/", json=body)

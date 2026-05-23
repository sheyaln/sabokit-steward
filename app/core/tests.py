"""Smoke tests covering Steward's no-auth surface + critical settings logic.

These exist primarily so pytest has something to collect and so CI catches
regressions in the routes Steward depends on remaining reachable without
authentication (healthz for orchestrators, access-denied / logged-out to
break OIDC redirect loops).
"""

from __future__ import annotations

import pytest
from django.test import Client

from core.models import AppSetting
from core.services import (
    admin_group_locked,
    admin_group_name,
    filter_groups,
    group_filter_regex,
)


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.mark.django_db
def test_healthz_returns_200(client: Client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.django_db
def test_access_denied_returns_403_without_auth(client: Client) -> None:
    response = client.get("/access-denied/")
    assert response.status_code == 403
    assert b"Access denied" in response.content


@pytest.mark.django_db
def test_logged_out_returns_200_without_auth(client: Client) -> None:
    """If this ever requires auth, the OIDC logout loops infinitely."""
    response = client.get("/logged-out/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_root_redirects_unauthenticated_to_oidc(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 302
    assert "/oidc/authenticate/" in response["Location"]


@pytest.mark.django_db
def test_appsetting_is_singleton() -> None:
    a = AppSetting.get()
    b = AppSetting.get()
    assert a.pk == b.pk == 1


@pytest.mark.django_db
def test_filter_groups_empty_pattern_passes_through() -> None:
    groups = [{"name": "union-electricians"}, {"name": "authentik Admins"}]
    s = AppSetting.get()
    s.group_filter_regex = ""
    s.save()
    assert filter_groups(groups) == groups


@pytest.mark.django_db
def test_filter_groups_applies_regex() -> None:
    groups = [
        {"name": "union-electricians", "pk": "a"},
        {"name": "committee-finance", "pk": "b"},
        {"name": "authentik Admins", "pk": "c"},
    ]
    s = AppSetting.get()
    s.group_filter_regex = "^(union|committee)-"
    s.save()
    out = filter_groups(groups)
    assert {g["pk"] for g in out} == {"a", "b"}


@pytest.mark.django_db
def test_filter_groups_invalid_regex_falls_back_to_all() -> None:
    """Invalid UI input must NOT lock admins out of group assignment."""
    groups = [{"name": "x"}, {"name": "y"}]
    s = AppSetting.get()
    s.group_filter_regex = "["
    s.save()
    assert filter_groups(groups) == groups


@pytest.mark.django_db
def test_admin_group_resolver_env_wins(settings) -> None:
    s = AppSetting.get()
    s.admin_group_name = "from-db"
    s.save()
    settings.AUTHENTIK_ADMIN_GROUP = "from-env"
    assert admin_group_name() == "from-env"
    assert admin_group_locked() is True


@pytest.mark.django_db
def test_admin_group_resolver_db_used_when_env_empty(settings) -> None:
    s = AppSetting.get()
    s.admin_group_name = "from-db"
    s.save()
    settings.AUTHENTIK_ADMIN_GROUP = ""
    assert admin_group_name() == "from-db"
    assert admin_group_locked() is False


@pytest.mark.django_db
def test_group_filter_resolver_env_wins(settings) -> None:
    s = AppSetting.get()
    s.group_filter_regex = "^db-"
    s.save()
    settings.AUTHENTIK_GROUP_FILTER = "^env-"
    assert group_filter_regex() == "^env-"

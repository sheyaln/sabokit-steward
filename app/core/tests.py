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


# ---------------------------------------------------------------------------
# /settings/ view: end-to-end POST behavior. These guard the UI flow that
# regressed silently in beta -- form looked plumbed-through but its save
# path had subtle bugs around env-locked fields and audit before-snapshot
# ordering.
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(username="shey", password="x", is_staff=True)


@pytest.fixture
def auth_client(admin_user) -> Client:
    import time as _t

    c = Client()
    c.force_login(admin_user)
    # SessionRefresh middleware kicks logged-in users without a valid OIDC
    # token expiration back to OIDC -- set one so login_required views work.
    session = c.session
    session["oidc_id_token_expiration"] = _t.time() + 3600
    session.save()
    return c


@pytest.mark.django_db
def test_settings_post_persists_group_filter_regex(auth_client, settings) -> None:
    settings.AUTHENTIK_GROUP_FILTER = ""
    settings.AUTHENTIK_INVITE_FLOW = ""
    settings.AUTHENTIK_ADMIN_GROUP = ""
    resp = auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "steward-admins",
            "invite_flow_slug": "",
            "group_filter_regex": "^(union|committee)-",
        },
    )
    assert resp.status_code == 302
    assert AppSetting.get().group_filter_regex == "^(union|committee)-"


@pytest.mark.django_db
def test_settings_post_persists_invite_flow_slug(auth_client, settings) -> None:
    settings.AUTHENTIK_INVITE_FLOW = ""
    settings.AUTHENTIK_ADMIN_GROUP = ""
    resp = auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "steward-admins",
            "invite_flow_slug": "default-source-enrollment",
            "group_filter_regex": "",
        },
    )
    assert resp.status_code == 302
    assert AppSetting.get().invite_flow_slug == "default-source-enrollment"


@pytest.mark.django_db
def test_settings_post_invalid_regex_rejected(auth_client, settings) -> None:
    settings.AUTHENTIK_GROUP_FILTER = ""
    settings.AUTHENTIK_ADMIN_GROUP = ""
    resp = auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "steward-admins",
            "invite_flow_slug": "",
            "group_filter_regex": "[unclosed",
        },
    )
    # Form re-renders with errors -- no redirect, no persistence.
    assert resp.status_code == 200
    assert AppSetting.get().group_filter_regex == ""
    assert b"Invalid regular expression" in resp.content


@pytest.mark.django_db
def test_settings_post_locked_field_ignores_user_input(auth_client, settings) -> None:
    """When AUTHENTIK_GROUP_FILTER is set, POSTed values for that field must
    not overwrite the DB value -- the env is authoritative."""
    s = AppSetting.get()
    s.group_filter_regex = "^db-was-here"
    s.save()
    settings.AUTHENTIK_GROUP_FILTER = "^env-pin"
    settings.AUTHENTIK_ADMIN_GROUP = ""
    resp = auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "steward-admins",
            "invite_flow_slug": "",
            "group_filter_regex": "^attacker-injected",
        },
    )
    assert resp.status_code == 302
    # Stored DB value untouched: env-locked means the form's input is dropped.
    assert AppSetting.get().group_filter_regex == "^db-was-here"


@pytest.mark.django_db
def test_settings_form_renders_env_value_not_db_default_when_locked(auth_client, settings) -> None:
    """If AUTHENTIK_ADMIN_GROUP=union-delegate but the DB still has the
    'steward-admins' default, the locked input must show 'union-delegate'
    -- the value that's actually in effect -- not the DB stale default."""
    settings.AUTHENTIK_ADMIN_GROUP = "union-delegate"
    s = AppSetting.get()
    s.admin_group_name = "steward-admins"
    s.save()
    resp = auth_client.get("/settings/")
    body = resp.content.decode()
    # The input element for admin_group_name should carry the env value.
    assert 'name="admin_group_name"' in body
    assert 'value="union-delegate"' in body
    # And the DB default must NOT appear as the input value.
    assert 'value="steward-admins"' not in body


@pytest.mark.django_db
def test_settings_post_locked_field_does_not_leak_env_into_db(auth_client, settings) -> None:
    """Even though the form displays the env value for a locked field,
    saving (regardless of what the user submits) must not write the env
    value into the DB row. Otherwise unsetting the env var later would
    surface the stale env value as if it were a real choice."""
    settings.AUTHENTIK_ADMIN_GROUP = "union-delegate"
    s = AppSetting.get()
    s.admin_group_name = "steward-admins"
    s.invite_flow_slug = ""
    s.group_filter_regex = ""
    s.save()
    resp = auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "anything",  # disabled -> ignored
            "invite_flow_slug": "",
            "group_filter_regex": "^foo-",
        },
    )
    assert resp.status_code == 302
    refreshed = AppSetting.get()
    # DB value untouched -- not "union-delegate", not "anything".
    assert refreshed.admin_group_name == "steward-admins"
    # Unlocked field DID save.
    assert refreshed.group_filter_regex == "^foo-"


@pytest.mark.django_db
def test_settings_group_filter_persists_across_other_requests(auth_client, settings) -> None:
    """User's repro: save a filter, visit /members/, come back to /settings/,
    the filter is gone. This must NOT happen -- no other code path mutates
    AppSetting, so the value has to survive."""
    settings.AUTHENTIK_GROUP_FILTER = ""
    settings.AUTHENTIK_ADMIN_GROUP = ""
    auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "steward-admins",
            "invite_flow_slug": "",
            "group_filter_regex": "^(union|committee)-",
        },
    )
    assert AppSetting.get().group_filter_regex == "^(union|committee)-"
    # Simulate visiting another page that reads AppSetting (filter_groups
    # triggers AppSetting.get()).
    from core.services import filter_groups

    filter_groups([{"name": "union-x"}, {"name": "other"}])
    assert AppSetting.get().group_filter_regex == "^(union|committee)-"
    # And re-render /settings/ to confirm the form shows the saved value.
    resp = auth_client.get("/settings/")
    assert 'value="^(union|committee)-"' in resp.content.decode()


@pytest.mark.django_db
def test_settings_post_with_blank_locked_field_does_not_clear_others(auth_client, settings) -> None:
    """Pre-fix repro of the disappearing-value bug: when the admin_group_name
    field is env-locked but the form submits *all* fields (browser sends
    every input), an earlier version of the view restored locked fields
    AFTER ModelForm mutated form.instance -- which was a no-op because
    form.instance IS the in-memory instance. Saving then persisted the
    POSTed (or blank) value for the locked field, and an audit-log diff
    that included it triggered a spurious mutation cascade.

    Concretely: lock admin_group_name via env, POST an entirely blank
    admin_group_name, and verify that all *unlocked* fields the user did
    set survive."""
    settings.AUTHENTIK_ADMIN_GROUP = "union-delegate"
    s = AppSetting.get()
    s.admin_group_name = "steward-admins"
    s.group_filter_regex = ""
    s.save()
    auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "",  # locked -> ignored, but browser submits empty
            "invite_flow_slug": "default-source-enrollment",
            "group_filter_regex": "^(union|committee)-",
        },
    )
    refreshed = AppSetting.get()
    assert refreshed.admin_group_name == "steward-admins"  # untouched
    assert refreshed.invite_flow_slug == "default-source-enrollment"
    assert refreshed.group_filter_regex == "^(union|committee)-"


@pytest.mark.django_db
def test_settings_post_audit_log_captures_real_before(auth_client, settings) -> None:
    """The audit row's before/after must reflect the actual transition,
    not after/after. Earlier code captured 'before' after ModelForm had
    already written cleaned_data into the instance."""
    from audit.models import AuditLog

    settings.AUTHENTIK_GROUP_FILTER = ""
    settings.AUTHENTIK_ADMIN_GROUP = ""
    s = AppSetting.get()
    s.group_filter_regex = "^old-"
    s.save()
    auth_client.post(
        "/settings/",
        data={
            "admin_group_name": "steward-admins",
            "invite_flow_slug": "",
            "group_filter_regex": "^new-",
        },
    )
    row = AuditLog.objects.filter(action=AuditLog.Action.SETTINGS_UPDATE).latest("created_at")
    assert row.before["group_filter_regex"] == "^old-"
    assert row.after["group_filter_regex"] == "^new-"

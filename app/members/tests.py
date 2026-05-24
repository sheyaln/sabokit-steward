"""End-to-end coverage for the member views.

These exist as a guard against the kind of breakage we hit during beta where
the group-filter regex looked plumbed-through but wasn't actually being
applied to what the UI rendered, and where the invitation flow path had
never been exercised end-to-end. Authentik is mocked at the
`core.authentik.AuthentikClient` boundary -- the point of these tests is
the Steward-side wiring, not Authentik's HTTP shape.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from core.models import AppSetting
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_user(username="shey", password="x", is_staff=True)


@pytest.fixture
def client(admin_user) -> Client:
    c = Client()
    c.force_login(admin_user)
    # mozilla-django-oidc's SessionRefresh middleware bounces logged-in users
    # whose `oidc_id_token_expiration` is missing or in the past. Without
    # this, every GET against a login_required view 302s to OIDC.
    session = c.session
    session["oidc_id_token_expiration"] = time.time() + 3600
    session.save()
    return c


def _fake_groups() -> list[dict]:
    return [
        {"pk": "uuid-union", "name": "union-electricians"},
        {"pk": "uuid-cmte", "name": "committee-finance"},
        {"pk": "uuid-admins", "name": "authentik Admins"},
        {"pk": "uuid-stewards", "name": "steward-admins"},
    ]


def _fake_user(pk: int = 7, **overrides) -> dict:
    base = {
        "pk": pk,
        "username": "alice@example.org",
        "name": "Alice Example",
        "email": "alice@example.org",
        "is_active": True,
        "attributes": {"x_number": "X-001"},
        "groups": ["uuid-union"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# member_list: the group dropdown must respect the group_filter_regex stored
# in AppSetting. This is the bug we got bit by in beta -- the resolver
# returned the right pattern but the view wasn't applying it.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_member_list_dropdown_filtered_by_regex(client, settings) -> None:
    settings.AUTHENTIK_GROUP_FILTER = ""
    s = AppSetting.get()
    s.group_filter_regex = "^(union|committee)-"
    s.save()
    fake = MagicMock()
    fake.list_users.return_value = {"results": [], "pagination": {}}
    fake.list_all_groups.return_value = _fake_groups()
    with patch("members.views.services.client", return_value=fake):
        resp = client.get("/members/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "union-electricians" in body
    assert "committee-finance" in body
    # The non-matching groups must NOT appear in the dropdown.
    assert "authentik Admins" not in body
    assert "steward-admins" not in body


@pytest.mark.django_db
def test_member_list_dropdown_unfiltered_when_regex_empty(client) -> None:
    s = AppSetting.get()
    s.group_filter_regex = ""
    s.save()
    fake = MagicMock()
    fake.list_users.return_value = {"results": [], "pagination": {}}
    fake.list_all_groups.return_value = _fake_groups()
    with patch("members.views.services.client", return_value=fake):
        resp = client.get("/members/")
    body = resp.content.decode()
    for name in ("union-electricians", "committee-finance", "authentik Admins", "steward-admins"):
        assert name in body


@pytest.mark.django_db
def test_member_list_dropdown_env_filter_wins(client, settings) -> None:
    """When AUTHENTIK_GROUP_FILTER is set, it shadows the DB value."""
    s = AppSetting.get()
    s.group_filter_regex = "^union"  # would match only one
    s.save()
    settings.AUTHENTIK_GROUP_FILTER = "^committee-"
    fake = MagicMock()
    fake.list_users.return_value = {"results": [], "pagination": {}}
    fake.list_all_groups.return_value = _fake_groups()
    with patch("members.views.services.client", return_value=fake):
        resp = client.get("/members/")
    body = resp.content.decode()
    assert "committee-finance" in body
    assert "union-electricians" not in body


# ---------------------------------------------------------------------------
# member_detail: filter applies to "Add to group" dropdown (available_groups),
# but a member who is ALREADY in a filtered-out group still sees that group
# under in_groups. Hiding it would silently lie about the member's state.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_member_detail_available_groups_filtered(client) -> None:
    s = AppSetting.get()
    s.group_filter_regex = "^(union|committee)-"
    s.save()
    fake = MagicMock()
    # alice has NO group memberships -- so all four groups would be available
    # if not for the filter.
    fake.get_user.return_value = _fake_user(groups=[])
    fake.list_all_groups.return_value = _fake_groups()
    fake.list_user_mfa_devices.return_value = []
    with (
        patch("members.views.services.client", return_value=fake),
        patch("members.services.client", return_value=fake),
    ):
        resp = client.get("/members/7/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # The "Add to group" select should only carry the two matching groups.
    assert 'value="uuid-union"' in body
    assert 'value="uuid-cmte"' in body
    assert 'value="uuid-admins"' not in body
    assert 'value="uuid-stewards"' not in body


@pytest.mark.django_db
def test_member_detail_shows_already_member_of_filtered_group(client) -> None:
    """A member belonging to a group the filter would hide must still see
    that membership listed -- otherwise the UI is silently lying about
    their state."""
    s = AppSetting.get()
    s.group_filter_regex = "^union"  # excludes "steward-admins"
    s.save()
    fake = MagicMock()
    fake.get_user.return_value = _fake_user(groups=["uuid-stewards"])
    fake.list_all_groups.return_value = _fake_groups()
    fake.list_user_mfa_devices.return_value = []
    with (
        patch("members.views.services.client", return_value=fake),
        patch("members.services.client", return_value=fake),
    ):
        resp = client.get("/members/7/")
    body = resp.content.decode()
    # In the "Groups" table, name appears for the existing membership.
    assert "steward-admins" in body


# ---------------------------------------------------------------------------
# Invitation flow: depends on (a) AppSetting.invite_flow_slug or env override
# being non-empty, (b) the flow existing in Authentik, (c) the invitation
# API call succeeding.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_member_no_invite_when_slug_empty(client) -> None:
    s = AppSetting.get()
    s.invite_flow_slug = ""
    s.save()
    fake = MagicMock()
    fake.create_user.return_value = _fake_user()
    with patch("members.services.client", return_value=fake):
        resp = client.post(
            "/members/new/",
            data={"name": "Alice Example", "email": "alice@example.org", "x_number": "X-001"},
        )
    # 302 to detail page indicates success.
    assert resp.status_code == 302
    fake.find_flow_by_slug.assert_not_called()
    fake.create_invitation.assert_not_called()


@pytest.mark.django_db
def test_create_member_creates_invitation_when_flow_exists(client) -> None:
    s = AppSetting.get()
    s.invite_flow_slug = "default-source-enrollment"
    s.save()
    fake = MagicMock()
    fake.create_user.return_value = _fake_user()
    fake.find_flow_by_slug.return_value = {
        "pk": "flow-uuid-abc",
        "slug": "default-source-enrollment",
    }
    fake.create_invitation.return_value = {"pk": "invite-uuid-xyz"}
    with patch("members.services.client", return_value=fake):
        resp = client.post(
            "/members/new/",
            data={"name": "Alice Example", "email": "alice@example.org", "x_number": "X-001"},
        )
    assert resp.status_code == 302
    fake.find_flow_by_slug.assert_called_once_with("default-source-enrollment")
    fake.create_invitation.assert_called_once()
    kwargs = fake.create_invitation.call_args.kwargs
    assert kwargs["flow_pk"] == "flow-uuid-abc"
    assert kwargs["single_use"] is True
    assert kwargs["fixed_data"] == {
        "username": "alice@example.org",
        "email": "alice@example.org",
        "name": "Alice Example",
    }


@pytest.mark.django_db
def test_create_member_skips_invite_when_flow_not_found(client) -> None:
    """User creation must still succeed; the missing flow is logged, not raised."""
    s = AppSetting.get()
    s.invite_flow_slug = "does-not-exist"
    s.save()
    fake = MagicMock()
    fake.create_user.return_value = _fake_user()
    fake.find_flow_by_slug.return_value = None
    with patch("members.services.client", return_value=fake):
        resp = client.post(
            "/members/new/",
            data={"name": "Alice Example", "email": "alice@example.org", "x_number": "X-001"},
        )
    assert resp.status_code == 302
    fake.create_invitation.assert_not_called()


@pytest.mark.django_db
def test_create_member_swallows_invite_api_error(client) -> None:
    """If the invitation API blows up, the member is already created --
    we don't want to surface that as a failure."""
    from core.authentik import AuthentikError

    s = AppSetting.get()
    s.invite_flow_slug = "default-source-enrollment"
    s.save()
    fake = MagicMock()
    fake.create_user.return_value = _fake_user()
    fake.find_flow_by_slug.return_value = {"pk": "flow-uuid", "slug": "default-source-enrollment"}
    fake.create_invitation.side_effect = AuthentikError("boom", status_code=500)
    with patch("members.services.client", return_value=fake):
        resp = client.post(
            "/members/new/",
            data={"name": "Alice Example", "email": "alice@example.org", "x_number": "X-001"},
        )
    assert resp.status_code == 302  # the member still made it through


@pytest.mark.django_db
def test_create_member_invitation_includes_enrollment_url(client, settings) -> None:
    """The admin needs a URL they can paste into Slack / email, not just
    an invitation pk -- otherwise the invite flow looks like it 'doesn't
    work' because there's nothing actionable to share."""
    settings.OIDC_OP_AUTHORIZATION_ENDPOINT = "https://auth.example.org/application/o/authorize/"
    s = AppSetting.get()
    s.invite_flow_slug = "default-source-enrollment"
    s.save()
    fake = MagicMock()
    fake.create_user.return_value = _fake_user()
    fake.find_flow_by_slug.return_value = {
        "pk": "flow-uuid",
        "slug": "default-source-enrollment",
    }
    fake.create_invitation.return_value = {"pk": "invite-uuid"}
    with patch("members.services.client", return_value=fake):
        resp = client.post(
            "/members/new/",
            data={"name": "Alice Example", "email": "alice@example.org", "x_number": "X-001"},
        )
    assert resp.status_code == 302
    msgs = [m.message for m in resp.wsgi_request._messages]
    expected = "https://auth.example.org/if/flow/default-source-enrollment/?itoken=invite-uuid"
    assert any(expected in m for m in msgs), msgs


@pytest.mark.django_db
def test_create_member_env_invite_flow_wins(client, settings) -> None:
    settings.AUTHENTIK_INVITE_FLOW = "env-flow"
    s = AppSetting.get()
    s.invite_flow_slug = "db-flow"
    s.save()
    fake = MagicMock()
    fake.create_user.return_value = _fake_user()
    fake.find_flow_by_slug.return_value = {"pk": "flow-uuid", "slug": "env-flow"}
    fake.create_invitation.return_value = {"pk": "invite-uuid"}
    with patch("members.services.client", return_value=fake):
        client.post(
            "/members/new/",
            data={"name": "Alice Example", "email": "alice@example.org", "x_number": "X-001"},
        )
    fake.find_flow_by_slug.assert_called_once_with("env-flow")


# ---------------------------------------------------------------------------
# Authentik client request shape -- guarding the wire format because
# Authentik silently 400s with cryptic messages on body-key mistakes.
# ---------------------------------------------------------------------------


def test_authentik_client_create_invitation_body_shape() -> None:
    from core.authentik import AuthentikClient

    with patch.object(AuthentikClient, "_request") as req:
        c = AuthentikClient(base_url="https://ak.example", token="t")
        c.create_invitation(
            name="inv-1",
            flow_pk="flow-uuid",
            fixed_data={"email": "x@example.org"},
            single_use=True,
        )
    req.assert_called_once()
    args, kwargs = req.call_args
    assert args[:2] == ("POST", "api/v3/stages/invitation/invitations/")
    assert kwargs["json"] == {
        "name": "inv-1",
        "flow": "flow-uuid",
        "fixed_data": {"email": "x@example.org"},
        "single_use": True,
    }


def test_authentik_client_list_all_groups_follows_pagination() -> None:
    """The single-page `list_groups` misses anything past the first 100
    groups, which silently breaks `group_filter_regex` against Authentik
    instances that have more groups than fit on one page."""
    from core.authentik import AuthentikClient

    pages = [
        {
            "results": [{"pk": "1", "name": "a"}, {"pk": "2", "name": "b"}],
            "pagination": {"next": 2},
        },
        {
            "results": [{"pk": "3", "name": "c"}],
            "pagination": {"next": 0},
        },
    ]
    with patch.object(AuthentikClient, "list_groups", side_effect=pages) as lg:
        c = AuthentikClient(base_url="https://ak.example", token="t")
        out = c.list_all_groups(page_size=2)
    assert [g["pk"] for g in out] == ["1", "2", "3"]
    # Should have stopped after seeing `next: 0` on page 2.
    assert lg.call_count == 2


def test_authentik_client_list_all_groups_stops_at_max_pages() -> None:
    """Pathological case: Authentik keeps reporting `next` indefinitely.
    The cap prevents an infinite loop."""
    from core.authentik import AuthentikClient

    forever = {"results": [{"pk": "x", "name": "n"}], "pagination": {"next": 999}}
    with patch.object(AuthentikClient, "list_groups", return_value=forever) as lg:
        c = AuthentikClient(base_url="https://ak.example", token="t")
        out = c.list_all_groups()
    assert len(out) == AuthentikClient.LIST_ALL_GROUPS_MAX_PAGES
    assert lg.call_count == AuthentikClient.LIST_ALL_GROUPS_MAX_PAGES


def test_authentik_client_find_flow_by_slug_query() -> None:
    from core.authentik import AuthentikClient

    with patch.object(AuthentikClient, "_request") as req:
        req.return_value = {"results": [{"pk": "flow-uuid", "slug": "foo"}]}
        c = AuthentikClient(base_url="https://ak.example", token="t")
        out = c.find_flow_by_slug("foo")
    assert out == {"pk": "flow-uuid", "slug": "foo"}
    args, kwargs = req.call_args
    assert args[:2] == ("GET", "api/v3/flows/instances/")
    assert kwargs["params"] == {"slug": "foo"}

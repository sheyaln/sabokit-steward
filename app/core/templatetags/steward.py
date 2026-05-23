from django import template
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def display_name(user) -> str:
    """Best-effort human-readable name for a User instance.

    Order: first_name (populated from the OIDC `given_name` claim) -> email
    claim -> the literal string "user". Returns "user" for anonymous or
    invalid input rather than blowing up at template render.
    """
    if not getattr(user, "is_authenticated", False):
        return _("user")
    first = (getattr(user, "first_name", "") or "").strip()
    if first:
        return first
    email = (getattr(user, "email", "") or "").strip()
    if email:
        return email
    return _("user")

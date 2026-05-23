"""Django settings for Steward.

All deployment-specific values are read from the environment (django-environ).
See .env.example for the full list.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    OIDC_RP_SIGN_ALGO=(str, "RS256"),
    OIDC_RP_SCOPES=(str, "openid profile email groups"),
    OIDC_VERIFY_SSL=(bool, True),
    OIDC_OP_END_SESSION_ENDPOINT=(str, ""),
    AUTHENTIK_API_URL=(str, ""),
    AUTHENTIK_API_TOKEN=(str, ""),
    # Empty defaults — when set, env wins and locks the matching field in the
    # /settings/ UI. Otherwise the DB value (core.AppSetting) is the source of
    # truth and is editable in the UI.
    AUTHENTIK_ADMIN_GROUP=(str, ""),
    AUTHENTIK_INVITE_FLOW=(str, ""),
    AUTHENTIK_GROUP_FILTER=(str, ""),
)

environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mozilla_django_oidc",
    "django_q",
    "core",
    "audit",
    "members",
    "imports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "mozilla_django_oidc.middleware.SessionRefresh",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "core.oidc.StewardOIDCBackend",
    "django.contrib.auth.backends.ModelBackend",
]

OIDC_RP_CLIENT_ID = env("OIDC_RP_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = env("OIDC_RP_CLIENT_SECRET")
OIDC_OP_AUTHORIZATION_ENDPOINT = env("OIDC_OP_AUTHORIZATION_ENDPOINT")
OIDC_OP_TOKEN_ENDPOINT = env("OIDC_OP_TOKEN_ENDPOINT")
OIDC_OP_USER_ENDPOINT = env("OIDC_OP_USER_ENDPOINT")
OIDC_OP_JWKS_ENDPOINT = env("OIDC_OP_JWKS_ENDPOINT")
OIDC_RP_SIGN_ALGO = env("OIDC_RP_SIGN_ALGO")
OIDC_RP_SCOPES = env("OIDC_RP_SCOPES")
OIDC_VERIFY_SSL = env("OIDC_VERIFY_SSL")
OIDC_CREATE_USER = True

LOGIN_URL = "oidc_authentication_init"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/logged-out/"
# When verify_claims rejects (e.g. user not in AUTHENTIK_ADMIN_GROUP),
# mozilla-django-oidc sends them here. Must NOT be a login-required URL or
# the OIDC flow loops infinitely against an already-authenticated Authentik
# session.
LOGIN_REDIRECT_URL_FAILURE = "/access-denied/"

# RP-initiated logout: redirect through Authentik's end-session endpoint so
# the IdP session dies too, not just Django's. Falls back to the local
# /logged-out/ page when OIDC_OP_END_SESSION_ENDPOINT is unset.
OIDC_OP_END_SESSION_ENDPOINT = env("OIDC_OP_END_SESSION_ENDPOINT")
OIDC_OP_LOGOUT_URL_METHOD = "core.oidc_logout.authentik_end_session"

AUTHENTIK_API_URL = env("AUTHENTIK_API_URL")
AUTHENTIK_API_TOKEN = env("AUTHENTIK_API_TOKEN")
AUTHENTIK_ADMIN_GROUP = env("AUTHENTIK_ADMIN_GROUP")
AUTHENTIK_INVITE_FLOW = env("AUTHENTIK_INVITE_FLOW")
AUTHENTIK_GROUP_FILTER = env("AUTHENTIK_GROUP_FILTER")

Q_CLUSTER = {
    "name": "steward",
    "workers": 2,
    "timeout": 600,
    "retry": 900,
    "queue_limit": 50,
    "bulk": 1,
    "orm": "default",
    "max_attempts": 1,
}

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("pt", "Português"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR.parent / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# syntax=docker/dockerfile:1.7
#
# Multi-stage build for Steward.
#   - builder: installs locked deps into a venv, runs collectstatic +
#     compilemessages with dummy env vars (real values come from the
#     deployment's .env at runtime).
#   - runtime: copies the venv, app source, and pre-collected static
#     into a slim image and runs as a non-root user.

# ---------------------------------------------------------------------- builder
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq5 \
        gettext \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /srv

# Layer-cache deps: install before copying source so changes to app code
# don't invalidate the dependency layer.
COPY pyproject.toml uv.lock /srv/
RUN uv sync --frozen --no-dev --no-install-project

COPY app /srv/app
WORKDIR /srv/app
RUN chmod +x /srv/app/entrypoint.sh

# Dummy env values that satisfy settings.py for build-time tasks. None of
# them affect the resulting artifacts (settings module is imported, but
# OIDC and database aren't actually contacted).
ENV DJANGO_SECRET_KEY=build-time-not-secret \
    DJANGO_DEBUG=false \
    DJANGO_ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite:////tmp/build.db \
    OIDC_RP_CLIENT_ID=build \
    OIDC_RP_CLIENT_SECRET=build \
    OIDC_OP_AUTHORIZATION_ENDPOINT=https://build.example/ \
    OIDC_OP_TOKEN_ENDPOINT=https://build.example/ \
    OIDC_OP_USER_ENDPOINT=https://build.example/ \
    OIDC_OP_JWKS_ENDPOINT=https://build.example/

RUN /opt/venv/bin/python manage.py collectstatic --noinput --clear \
    && /opt/venv/bin/python manage.py compilemessages

# ---------------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ARG STEWARD_VERSION=0.0.0
ARG STEWARD_VCS_REF=unknown
ARG BUILD_DATE

LABEL org.opencontainers.image.title="Steward" \
      org.opencontainers.image.description="Simplified UI for managing Authentik users and groups." \
      org.opencontainers.image.url="https://github.com/sheyaln/sabokit-steward" \
      org.opencontainers.image.source="https://github.com/sheyaln/sabokit-steward" \
      org.opencontainers.image.version="${STEWARD_VERSION}" \
      org.opencontainers.image.revision="${STEWARD_VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

# Runtime needs libpq5 for psycopg, no build toolchain. curl is for the
# HEALTHCHECK; ca-certificates so requests can talk to HTTPS Authentik.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 steward \
    && useradd --system --uid 1001 --gid steward --home-dir /srv --shell /usr/sbin/nologin steward

COPY --from=builder --chown=steward:steward /opt/venv /opt/venv
COPY --from=builder --chown=steward:steward /srv/app /srv/app
COPY --from=builder --chown=steward:steward /srv/staticfiles /srv/staticfiles

WORKDIR /srv/app
USER steward

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/srv/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000", "--workers=3", "--access-logfile=-"]

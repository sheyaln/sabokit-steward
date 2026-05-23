# Ops runbook

For whoever's operating Steward. Assumes you know Docker, Django, and
Authentik.

## Architecture in one paragraph

Django 5 webapp + a Django-Q sidecar (`qcluster`) for bulk import jobs,
both backed by a small Postgres for Steward's own state (audit log,
import jobs, sessions, Django-Q queue). All actual user state lives in
Authentik -- Steward holds no mirror. Traefik / nginx / Caddy in front
for TLS.

```
browser ──(HTTPS)──> reverse proxy ──> steward-web ──(HTTPS)──> Authentik
                                              │
                                              ├─> Postgres (steward DB)
                                              └─> steward-qcluster ──> Authentik
```

## Dev

```bash
cp .env.example .env
docker compose -f deploy/compose/docker-compose.yml --profile authentik up -d
```

Without `--profile authentik` you get just Steward + its Postgres, useful
when pointing at an external Authentik.

Test users from the blueprint:

| User | Password | Notes |
| --- | --- | --- |
| `alice` | `alice-dev` | in `steward-admins` + `steward-members` |
| `bob` | `bob-dev` | not in `steward-admins`; will be rejected by Steward |
| `shey` | `shey-dev` | `steward-admins` + `authentik Admins` |
| `akadmin` | `akadmin` | for the Authentik admin UI itself |

Reset everything:

```bash
docker compose -f deploy/compose/docker-compose.yml --profile authentik down -v
docker compose -f deploy/compose/docker-compose.yml --profile authentik up -d
```

Volumes wipe; the blueprint at
`deploy/compose/authentik-blueprints/steward.yaml` rebuilds Authentik's
state on the next boot. Anything I added via the Authentik UI (not the
blueprint) is gone after a wipe -- if I want persistence across wipes,
it goes in the blueprint.

## Production via plain docker compose

There's a ready compose file at `deploy/compose/docker-compose.prod.yml`.
Drop it on the host, write a `.env` with the required values (see
[README](../README.md)), put a TLS-terminating proxy in front.

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f web
```

## Production via federated-commons

If I'm deploying on a federated-commons stack, the Steward bundle is at
`platform/apps/steward/` over there. Enable it in `terraform.tfvars`:

```hcl
apps = {
  steward = {
    enabled  = true
    hostname = "members.example.org"
  }
}
```

The Terraform there provisions everything; the Ansible role pulls a
signed image from GHCR, renders `/opt/steward/.env`, brings up
`docker-compose` with `web` + `qcluster`.

## Migrations

Run automatically on container start by `app/entrypoint.sh`. The
`qcluster` sidecar opts out via `STEWARD_RUN_MIGRATIONS=0` so only one
process tries.

Force one by hand:

```bash
docker compose exec web python manage.py migrate
```

## Static files

Baked into the production image at build time. `STEWARD_COLLECTSTATIC=1`
(the default) re-runs `collectstatic` on container start; set `0` for
sidecars that don't need it. Whitenoise serves them from the `web`
container; no static-files volume needed except for media uploads
(mounted at `/srv/media`).

## Branch protection on master

`scripts/setup-branch-protection.sh`. Re-runnable; safe on top of an
existing configuration. Enforces required, strict status checks
(`lint`, `test`, `image`), PR-required merges, no force push, no
deletion, conversation resolution.

```bash
scripts/setup-branch-protection.sh                  # defaults (review_count=0)
REVIEW_COUNT=1 scripts/setup-branch-protection.sh   # require 1 approving review
```

I leave `enforce_admins=false` so I can break-glass if CI gets stuck.

## Verifying a release before deploying

Every image published from `master` or a `v*` tag is signed by CI
(cosign keyless via GitHub OIDC) and ships with SLSA build provenance +
SBOM. Verify before pinning a tag in Ansible / docker-compose:

```bash
IMAGE=ghcr.io/sheyaln/sabokit-steward:v0.1.0-beta

# 1. Signature -- proves CI built it from this repo.
cosign verify "$IMAGE" \
  --certificate-identity-regexp "^https://github.com/sheyaln/sabokit-steward/.github/workflows/" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

# 2. Build provenance -- which commit, workflow, runner.
gh attestation verify --owner sheyaln "oci://$IMAGE"

# 3. SBOM -- skim for unexpected components.
cosign download sbom "$IMAGE" | jq '.predicate.packages[].name' | sort -u | head
```

If any of those fail, don't deploy. Treat it as a possible supply-chain
compromise; check the CI run for the build and figure out what
happened.

## Updating

Bump the image tag (`apps.steward.image_tag` in federated-commons, or
`STEWARD_IMAGE_TAG` env var for the plain compose path), run
`terraform apply` / `docker compose up -d`. The Ansible role uses
`pull: always`; plain compose users want
`docker compose pull && docker compose up -d`.

## Logs

```bash
docker logs --tail 200 -f steward-web
docker logs --tail 200 -f steward-qcluster
```

OIDC rejections look like:

```
WARNING Rejecting OIDC login for bob@example.org: missing required group steward-admins
```

That's not an error condition. It's the gating doing its job.

## Common issues

**Login loops back to the OIDC start.** The wrong account is signed in
to Authentik (not in the admin group). Steward sends them to
`/access-denied/`, which has a "Sign out of Authentik" button. Or
clear browser cookies for the Authentik host.

**Login loops, but the loop is `/oidc/callback/` ↔ `/`.** Check that
`OIDC_OP_END_SESSION_ENDPOINT` is set in the env -- without it, "Log
out" only clears Django's session and SSO immediately re-auths.

**Login redirects loop or land on an Authentik error page.** Check
that the `redirect_uris` in Authentik exactly match
`<hostname>/oidc/callback/`. Renaming the host means re-running
Terraform (or updating the OAuth provider in Authentik directly).

**"Authentik API error: 401" in the UI.** The service-account API token
is gone or rotated. Mint a new one in Authentik, drop it into the
`.env` (or the federated-commons app-secrets bag + re-apply Terraform).

**Bulk import stuck in `running`.** The `qcluster` sidecar isn't picking
tasks. `docker logs steward-qcluster` -- the cluster heartbeat should
print every 30 s. Restart it if silent.

**Audit log missing rows you expected.** Most common cause: a view or
task called `AuthentikClient` directly instead of going through
`members.services.*` / `imports.services.*`. Grep `AuthentikClient(`
to find the offender.

**Migrations conflict on deploy.** Don't amend a migration that landed
on master; add a new one. The entrypoint runs `migrate --noinput`, so
an interactive conflict fails the boot loudly.

## Backups

The Steward DB holds audit log + bulk-import history. Both matter for
forensics; neither matters for member state itself (Authentik owns
that). Back it up alongside Authentik.

Restore order: Authentik first, then Steward. Otherwise the audit log
references Authentik PKs that don't exist yet.

## Health check

`GET /healthz` returns `ok` (200). Used by the image-level HEALTHCHECK
and the dev/prod compose configs. Point the reverse proxy at it too if
you want fast failover.

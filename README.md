# Steward

A simplified UI for managing Authentik users and groups -- add, edit,
activate/deactivate members, assign them to groups, bulk-import from CSV,
audit everything. It talks to Authentik over the REST API; Authentik stays
the source of truth.

Works against any Authentik instance. I built it for use with the
[federated-commons](https://github.com/sheyaln/federated-commons) blueprint
but there's nothing in it that requires federated-commons -- give it the
OIDC client credentials, a service-account API token, and a hostname, and
it goes.

## What's in scope

- list, add, edit members (name, email, X-Number) against Authentik
- activate / deactivate
- assign members to existing groups
- bulk-import from CSV (dry-run preview, idempotent on email)
- per-member password-reset email trigger
- per-member MFA device removal
- audit log of every change Steward makes, with a viewer
- multi-language UI (en, es, fr, de, it, pt scaffolded)

## What's out of scope

- group creation -- group taxonomy is a sysadmin job
- SMTP -- Authentik handles email
- a self-service member portal -- Steward is for *admins*
- mirroring user state locally

## Status

Beta. I run it. Single maintainer (me).

## Stack

Django 5.1 · PostgreSQL · Django-Q2 · `mozilla-django-oidc` · `requests`

## Run it locally

The dev compose bundles its own Authentik so you don't need to wire up an
external IdP just to play with it.

```bash
git clone https://github.com/sheyaln/sabokit-steward.git ~/steward
cd ~/steward
cp .env.example .env
docker compose -f deploy/compose/docker-compose.yml --profile authentik up -d
```

Wait ~30 s for the Authentik blueprint to apply, then open
`http://localhost:8000` and sign in as **`alice`** / `alice-dev`. Test
users + groups + the OIDC provider are all provisioned from
`deploy/compose/authentik-blueprints/steward.yaml` -- `down -v` wipes
volumes, `up` brings everything back.

## Run it in production

```bash
mkdir -p /opt/steward && cd /opt/steward
curl -fsSLo docker-compose.yml https://raw.githubusercontent.com/sheyaln/sabokit-steward/master/deploy/compose/docker-compose.prod.yml

# Create .env with:
#   DJANGO_SECRET_KEY=<long random string>
#   DJANGO_DEBUG=false
#   DJANGO_ALLOWED_HOSTS=members.example.org
#   POSTGRES_PASSWORD=<random>
#   OIDC_RP_CLIENT_ID=<from Authentik>
#   OIDC_RP_CLIENT_SECRET=<from Authentik>
#   OIDC_OP_AUTHORIZATION_ENDPOINT=https://auth.example.org/application/o/authorize/
#   OIDC_OP_TOKEN_ENDPOINT=https://auth.example.org/application/o/token/
#   OIDC_OP_USER_ENDPOINT=https://auth.example.org/application/o/userinfo/
#   OIDC_OP_JWKS_ENDPOINT=https://auth.example.org/application/o/steward/jwks/
#   OIDC_OP_END_SESSION_ENDPOINT=https://auth.example.org/application/o/steward/end-session/
#   AUTHENTIK_API_URL=https://auth.example.org
#   AUTHENTIK_API_TOKEN=<service-account token>
#
# Then:
docker compose up -d
```

Put Traefik / nginx / Caddy in front of port 8000 for TLS -- the bundled
compose only binds to `127.0.0.1`.

In Authentik you need an OAuth2/OpenID provider + application
(redirect URI `https://<your-host>/oidc/callback/`), and a service account
whose token Steward uses for the admin API (the service account needs
permission to manage users and groups).

## License

MIT. See [LICENSE](./LICENSE).

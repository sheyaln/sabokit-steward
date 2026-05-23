# Contributing

I built Steward to scratch my own itch. I'm happy to take PRs that match
that itch -- a simpler Authentik admin UI for non-technical members of
organizations I work with.

## Before you open a PR

- Open an issue first if it's anything beyond a small fix. Saves both of
  us time if the direction doesn't fit.
- Match the existing tone in code + docs. Comments explain *why*, not
  what (the code already says what).
- One feature or fix per PR.

## Local setup

```bash
cp .env.example .env
docker compose -f deploy/compose/docker-compose.yml --profile authentik up -d
```

The README has the rest of the dev story.

## Coding conventions

- `ruff format` + `ruff check` (config in `pyproject.toml`). CI gates on
  both.
- `pytest` from repo root. The CI workflow runs against real Postgres.
- Migrations get committed alongside model changes -- including the ones
  Django produces for `verbose_name` tweaks.

## The audit-log rule

Anything that mutates Authentik must go through `members.services.*` or
`imports.services.*`. Those wrappers write an `AuditLog` row in the same
call. Calling `core.authentik.AuthentikClient` directly from a view
silently bypasses the audit trail -- don't.

If your change adds a new kind of mutation, add a new
`AuditLog.Action` value and the corresponding `record()` call.

## i18n

Wrap user-facing strings in Python with `gettext_lazy` (`_("...")`) and
in templates with `{% trans %}` / `{% blocktrans %}`. After adding or
changing strings:

```bash
docker compose -f deploy/compose/docker-compose.yml exec -w /srv/app web \
    python manage.py makemessages --all
```

Then translate. `docs/i18n.md` has the full workflow.

## PRs

- Title format matters: Release Drafter auto-categorizes by the prefix
  (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `deps:`, `sec:`,
  `feat!:` for breaking). Mislabel and your PR lands in the wrong
  bucket of the next release notes.
- Add a `CHANGELOG.md` entry under `## [Unreleased]` for anything a
  user would notice.
- `manage.py check --deploy` should stay clean.
- Tests for new behavior where it's practical.

## Security

See [SECURITY.md](./SECURITY.md). Don't file security bugs as issues.

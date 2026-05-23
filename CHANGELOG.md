# Changelog

Notable changes to Steward. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); SemVer from
v1.0.0 onward.

## [Unreleased]

## [0.1.0-beta] - 2026-05-23

First public beta. Single maintainer; pre-1.0.

### Added

- OIDC login against Authentik with admin-group gating.
- Member CRUD via the Authentik admin API: list, add, edit, activate /
  deactivate. Three fields exposed: name, email, X-Number (attribute).
- Group assignment: add / remove members to existing Authentik groups.
- Group filter (regex) so the UI surfaces only the groups you care about
  (e.g. `^(union|committee)-`). Configurable in `/settings/` or via
  `AUTHENTIK_GROUP_FILTER`.
- Per-member password-reset trigger (uses Authentik's recovery email).
- Per-member MFA device removal.
- Bulk CSV import: upload → dry-run preview → idempotent apply via
  Django-Q. Per-row report.
- Append-only audit log + viewer. Every mutating Authentik call writes
  a row.
- Editable app settings at `/settings/`: admin group, invite flow,
  group filter. Env vars shadow + lock the matching field when set.
- RP-initiated OIDC logout that terminates the Authentik session too,
  not just Steward's. `/logged-out/` landing page breaks the silent
  re-login loop.
- Internationalization scaffolding: `LocaleMiddleware`, message
  catalogues for en, es, fr, de, it, pt.
- Local dev stack: docker-compose with optional `--profile authentik`
  that auto-provisions provider, scope mappings, service-account API
  token, groups, and test users via blueprint.
- federated-commons bundle (Terraform + Ansible) at
  `platform/apps/steward/` in that repo.
- Production docker-compose at `deploy/compose/docker-compose.prod.yml`
  pulling the published image from GHCR.
- Multi-stage Dockerfile: locked deps via `uv.lock`, non-root user,
  baked static + compiled message catalogues, OCI labels, built-in
  `/healthz` HEALTHCHECK.
- CI pipeline: ruff, pytest against real Postgres, `manage.py check
  --deploy`, image build + `/healthz` smoke, Trivy scan (SARIF
  uploaded). On master / `v*` tags, multi-arch push to GHCR.
- Supply-chain attestation on publish: cosign keyless signature, SLSA
  build provenance, SBOM. Verification recipe in
  `docs/ops-runbook.md`.
- Renovate config for grouped, scheduled dep updates.
- Release Drafter for PR-driven release notes with title autolabeling.
- Branch protection script (`scripts/setup-branch-protection.sh`).

[Unreleased]: https://github.com/sheyaln/sabokit-steward/compare/v0.1.0-beta...HEAD
[0.1.0-beta]: https://github.com/sheyaln/sabokit-steward/releases/tag/v0.1.0-beta

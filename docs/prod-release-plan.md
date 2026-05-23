# Release pipeline

This was a plan once. It's all built now. Keeping the doc as the
shortest possible reference to what's wired up + where to change it.

## The bar

- **Reproducible.** A tag at commit `abc123` builds the same image on
  my box and in CI -- locked deps in `uv.lock`, base image will be
  SHA-pinned on the first Renovate sweep.
- **Signed + attested.** Cosign keyless signature + SLSA provenance +
  SBOM on every published image. Verification recipe in
  [ops-runbook.md](./ops-runbook.md#verifying-a-release-before-deploying).
- **Tested before publish.** Lint, pytest against real Postgres,
  `manage.py check --deploy`, image build + `/healthz` smoke, Trivy
  HIGH/CRITICAL -- all gate publication.
- **Patchable.** Renovate opens PRs on a schedule; security alerts
  open immediately. Merging the PR is the patch.
- **Small attack surface.** Multi-stage image: no build toolchain, no
  package manager in the runtime layer, runs as non-root `steward`.

## Where it all lives

| Concern | File |
| --- | --- |
| CI (lint + test + check + build + sign + scan) | `.github/workflows/ci.yml` |
| Release notes draft | `.github/release-drafter.yml` + `.github/workflows/release-drafter.yml` |
| Dependency PRs | `renovate.json` |
| Branch protection | `scripts/setup-branch-protection.sh` |
| Image | `deploy/compose/Dockerfile` + `uv.lock` |
| PR checklist | `.github/PULL_REQUEST_TEMPLATE.md` |
| Trivy exceptions | `.trivyignore` (empty; add only with a reason) |

## Cutting a release

I label PRs with a conventional prefix (`feat:`, `fix:`, `docs:`,
`deps:`, `feat!:` for breaking). Release Drafter accumulates them into
a draft release in the GitHub UI as I go. When I'm ready:

1. Edit the draft to taste in the GitHub UI.
2. Publish the draft. That creates a `v*` tag.
3. The tag fires `ci.yml` again, which pushes the multi-arch image,
   signs it, attaches provenance + SBOM, and runs Trivy. Once it's
   green the tag is deployable.
4. Bump `apps.steward.image_tag` (federated-commons) or
   `STEWARD_IMAGE_TAG` (plain compose) on the host. Verify with
   `cosign verify` before pulling.

## Things I held back from Renovate

- Django majors. LTS coordination is manual.
- The dev Authentik image (`deploy/compose/docker-compose.yml`).
  Blueprint compat changes between Authentik versions; I want to
  bump that on my own schedule.

Everything else flows through Renovate.

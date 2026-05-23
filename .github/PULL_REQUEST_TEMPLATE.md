<!--
Title convention (drives Release Drafter labeling automatically):
  feat: ...        -> Features
  fix: ...         -> Bug fixes
  docs: ...        -> Documentation
  chore: ...       -> Maintenance
  refactor: ...    -> Maintenance
  sec: ...         -> Security
  deps: ...        -> Dependencies
  feat!: ...       -> Breaking changes
You can also add a label by hand to override.
-->

## What this changes

<!-- One or two sentences. The WHY, not the WHAT (the diff has the what). -->

## Checklist

- [ ] Tests added or updated (or N/A — describe why)
- [ ] Migration committed if a model changed
- [ ] `CHANGELOG.md` entry added under `## [Unreleased]`
- [ ] `AuditLog` row written if a mutating Authentik action was added
- [ ] `manage.py check --deploy` clean

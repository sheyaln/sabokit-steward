#!/usr/bin/env bash
# Apply branch protection to the Steward repo's default branch.
#
# Re-runnable. Run after the CI workflow has been pushed at least once
# (GitHub registers required status checks by NAME, so the workflow's
# `lint`, `test`, `image` jobs need to exist in the repo for the listed
# contexts to take effect).
#
# Usage:
#   scripts/setup-branch-protection.sh                  # defaults: sheyaln/sabokit-steward master
#   scripts/setup-branch-protection.sh sheyaln/sabokit-steward master
#   REVIEW_COUNT=1 scripts/setup-branch-protection.sh   # require 1 approving review
#
# Requires: gh CLI, authenticated to a token with admin:repo on the target.

set -euo pipefail

REPO="${1:-sheyaln/sabokit-steward}"
BRANCH="${2:-master}"
REVIEW_COUNT="${REVIEW_COUNT:-0}"

echo "→ applying branch protection to ${REPO}@${BRANCH} (review_count=${REVIEW_COUNT})"

gh api -X PUT "/repos/${REPO}/branches/${BRANCH}/protection" --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "test", "image"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": ${REVIEW_COUNT},
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": true,
  "block_creations": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

echo "✓ branch protection applied"
echo
echo "Current settings:"
gh api "/repos/${REPO}/branches/${BRANCH}/protection" --jq '{
  required_status_checks: .required_status_checks,
  required_pull_request_reviews: .required_pull_request_reviews,
  allow_force_pushes: .allow_force_pushes.enabled,
  allow_deletions: .allow_deletions.enabled,
  enforce_admins: .enforce_admins.enabled
}'

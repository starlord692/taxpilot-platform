# Contributing to TaxPilot AI

## Branches

- `main` contains production-ready code.
- `develop` is the integration branch for completed feature work.
- `feature/ep-xxx-feature-name` branches contain individual engineering packs.
- `release/vX.Y.Z` branches are temporary stabilization branches.
- `hotfix/short-description` branches contain urgent production corrections.

## Standard workflow

1. Update local `develop` from `origin/develop`.
2. Create `feature/ep-xxx-feature-name` from `develop`.
3. Commit focused, reviewable changes.
4. Open a pull request into `develop`.
5. Create a temporary versioned release branch from `develop` when preparing a release.
6. Merge the stabilized release into `main`, tag it, and merge the release back into `develop`.
7. Delete the temporary release branch.

Never commit feature work directly to `main`.

## Recommended GitHub branch protection

Configure these rules manually for `main`:

- Protect the branch from direct pushes and force pushes.
- Require pull requests before merging.
- Require passing test and build checks when CI is introduced.
- Require at least one approving code review.
- Require conversations to be resolved before merging.

Apply equivalent pull-request protection to `develop`, while allowing approved release-management workflows.

## Pull requests

- Keep each pull request focused on one engineering pack or operational change.
- Describe verified API changes, migrations, tests, and rollout risks.
- Require passing checks and at least one review before merging.
- Prefer squash merges for feature branches unless preserving individual commits adds clear value.

## Commit messages

Use conventional prefixes such as `feat:`, `fix:`, `docs:`, `test:`, `chore:`, and `refactor:`.

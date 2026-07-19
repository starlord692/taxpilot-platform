# Git Workflow

## Long-lived branches

- `main` — production-ready history.
- `develop` — integration history for completed engineering packs.

## Temporary branches

- `feature/ep-xxx-feature-name` — branched from and merged into `develop`.
- `release/vX.Y.Z` — created from `develop` during release stabilization, merged into both `main` and `develop`, then deleted.
- `hotfix/short-description` — created from `main`, merged into both `main` and `develop`, then deleted.

## Promotion flow

```text
feature/* → develop → release/vX.Y.Z → main
                    ↖─────────────────┘
```

No application development occurs directly on `main`.

## Branch protection recommendation

GitHub administrators should protect `main`, require pull requests, require passing tests and builds after CI is introduced, require at least one approving review, block force pushes, and require review conversations to be resolved. These controls are documented only; this repository scaffold does not configure them automatically.

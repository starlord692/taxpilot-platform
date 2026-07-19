# TaxPilot AI Platform

TaxPilot AI is an AI-powered Business Operating System for MSMEs, freelancers, and small businesses.

## Repository layout

- `backend/` — FastAPI services and domain modules.
- `frontend/` — Next.js application.
- `docs/` — Product, architecture, API, decision, roadmap, meeting, and design documentation.

## Branch workflow

```text
feature/* → develop → release/vX.Y.Z → main
                          hotfix/* → main
```

Development must not occur directly on `main`. Feature work starts from `develop` and returns through a pull request. Release branches are temporary and versioned.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete workflow.

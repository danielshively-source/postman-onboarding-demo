# postman-onboarding-demo

An **idempotent** GitHub Actions pipeline that runs the full
[Postman API Onboarding](https://github.com/postman-cs/postman-api-onboarding-action)
suite on every push to `main`.

## What the pipeline does

The workflow at [`.github/workflows/postman-onboarding.yml`](.github/workflows/postman-onboarding.yml)
chains the Postman onboarding actions via the composite entrypoint:

1. **Resolve service token** (`postman-resolve-service-token-action`) — mints a fresh
   service-account access token and resolves the team ID from the `POSTMAN_API_KEY`.
2. **Bootstrap** (`postman-bootstrap-action`) — creates/reuses the workspace, uploads
   `openapi/core-payments-openapi.yaml` to Spec Hub, and generates the baseline, smoke,
   and contract collections.
3. **Repo sync** (`postman-repo-sync-action`) — exports collection/environment artifacts
   into this repo, registers a mock server and smoke monitor, and persists asset IDs.
4. **Smoke + contract tests** — runs the generated collections with the Postman CLI and
   uploads JUnit results as a workflow artifact.
5. **Insights linking** (`postman-insights-onboarding-action`) — links discovered services
   to the workspace (`enable-insights: true`).

## Why it's idempotent

- The onboarding action **creates or reuses** the workspace, spec, and collections, so
  re-runs update in place instead of duplicating assets.
- `collection-sync-mode: refresh` and `spec-sync-mode: update` update tracked assets
  rather than minting new versions.
- `repo-write-mode: commit-and-push` persists resolved asset IDs (`.postman/resources.yaml`)
  back to the repo so later runs reuse them.
- `concurrency` serializes runs on `main` so two pushes never race to provision the same assets.
- Commits pushed back by the action use `GITHUB_TOKEN`, which **does not** re-trigger the
  workflow (GitHub blocks recursive `GITHUB_TOKEN` triggers). `paths-ignore` is a second guard.

## Required secrets

| Secret | Purpose |
| --- | --- |
| `POSTMAN_API_KEY` | Service-account Postman API key (`PMAK-*`). Bootstraps all assets and mints the access token. |
| `POSTMAN_ACCESS_TOKEN` | Pre-supplied access token. Not used by default (the pipeline mints one); available as an alternative — see the comment in the workflow. |

## Trigger

Push to `main` (or run manually via **workflow_dispatch**). Replace
`openapi/core-payments-openapi.yaml` with your own OpenAPI document to onboard a real service.

# FloQast API Pipeline (CSE proof)

A runnable CSE pipeline that proves Postman can take FloQast's **first external-ready
APIs** and turn them into **governed, discoverable, CI-enforced, agent-ready** Postman
assets - without forcing a rewrite of their existing GitHub, monorepo, and test setup.

> The governance gate runs **today with no Postman credentials**. The live-Postman
> stages (workspace import, catalog publish, runtime insights) switch on with one repo
> variable once a valid Postman key is configured.

Full write-up: **[docs/PIPELINE.md](docs/PIPELINE.md)**.

## What's here

| Path | Purpose |
| --- | --- |
| `governance/floqast.spectral.yaml` | The "Stripe-level" governance ruleset (blocker vs flag) |
| `scripts/agent_readiness.py` | 0-100 agent-readiness / UI-vs-agent scorer |
| `openapi/core-payments-openapi.yaml` | Compliant reference spec (passes the gate, scores 100) |
| `examples/non-compliant/legacy-internal-api.yaml` | Fixture that fails the gate (15 blockers) - proves enforcement |
| `.github/workflows/api-pipeline.yml` | Staged pipeline: governance -> onboard+catalog -> insights |
| `docs/PIPELINE.md` | Maps the 6 jobs, 10-step flow, no-rewrite matrix, security checkpoint, MCP track |

## The gate, the most important part

`error` = **blocker** (fails CI, not ready to publish). `warn` = **flag** (surfaced, non-blocking).
Nothing reaches Postman unless the spec passes (`onboard` `needs: governance`).

```bash
# Compliant reference -> exit 0
npx @stoplight/spectral-cli lint openapi/core-payments-openapi.yaml \
  --ruleset governance/floqast.spectral.yaml --fail-severity error
python3 scripts/agent_readiness.py openapi/core-payments-openapi.yaml      # 100/100 agent-ready

# Legacy internal API -> 15 blockers, exit 1
npx @stoplight/spectral-cli lint examples/non-compliant/legacy-internal-api.yaml \
  --ruleset governance/floqast.spectral.yaml --fail-severity error
python3 scripts/agent_readiness.py examples/non-compliant/legacy-internal-api.yaml  # 17.5/100 ui-oriented
```

## Pipeline stages

```
push to main / PR / dispatch
        |
        v
[ governance ]  Spectral Stripe-level lint + agent-readiness score   (ALWAYS, BLOCKING)
        |  needs: governance, if POSTMAN_LIVE == true
        v
[ onboard ]     import spec -> workspace/collections -> repo sync -> catalog foundation
        |  needs: onboard, if INSIGHTS_SECURITY_APPROVED == true
        v
[ insights ]    runtime observability (only after security sign-off)
```

## Trigger & idempotency

- Triggers on **push to `main`**, **pull requests**, and **workflow_dispatch**.
- Idempotent: create-or-reuse Postman assets, `refresh`/`update` sync modes, serialized
  `concurrency`, and `GITHUB_TOKEN` pushes that don't recursively re-trigger the workflow.

## Secrets & variables

| Name | Type | Purpose |
| --- | --- | --- |
| `POSTMAN_API_KEY` | secret | Service-account PMAK. Required for live stages. |
| `POSTMAN_ACCESS_TOKEN` | secret | Optional pre-supplied access token (alternative to minting). |
| `POSTMAN_LIVE` | variable | `true` enables the `onboard` job. |
| `INSIGHTS_SECURITY_APPROVED` | variable | `true` (after sign-off) enables the `insights` job. |

See [docs/PIPELINE.md](docs/PIPELINE.md#turning-on-the-live-postman-stages) to go live.

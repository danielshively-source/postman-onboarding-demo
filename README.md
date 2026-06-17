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
| `scripts/render_governance.py` | Renders the demo scorecard + inline PR annotations + the gate |
| `openapi/*.yaml` | Sample external-ready specs (see catalog below) |
| `examples/non-compliant/legacy-internal-api.yaml` | Fixture that fails the gate (15 blockers) - proves enforcement |
| `.github/workflows/api-pipeline.yml` | Staged pipeline: governance -> onboard+catalog -> insights |
| `docs/PIPELINE.md` | Maps the 6 jobs, 10-step flow, no-rewrite matrix, security checkpoint, MCP track |

## Sample spec catalog

A small batch standing in for FloQast's "first external-ready APIs," chosen to show the
full range of the gate. Pick any of them on a manual run (**Actions -> FloQast API
Pipeline -> Run workflow -> Spec**).

| Spec | Domain | Governance gate | Agent-readiness |
| --- | --- | --- | --- |
| `openapi/reconciliations.yaml` | Account reconciliations | :white_check_mark: PASS | **100** - agent-ready |
| `openapi/core-payments-openapi.yaml` | Payments (generic) | :white_check_mark: PASS | **100** - agent-ready |
| `openapi/close-tasks.yaml` | Close checklist tasks | :white_check_mark: PASS | **70** - needs-work |
| `examples/non-compliant/legacy-internal-api.yaml` | Legacy internal API | :x: FAIL (15 blockers) | **17.5** - ui-oriented |

`close-tasks.yaml` is the instructive middle case: it **passes governance** yet is flagged
**needs-work** for agents (no examples, undocumented schema properties, no documented errors
on reads) - exactly the "compliant but not yet agent-ready" distinction Raaj asked about.

## The gate, the most important part

`error` = **blocker** (fails CI, not ready to publish). `warn` = **flag** (surfaced, non-blocking).
Nothing reaches Postman unless the spec passes (`onboard` `needs: governance`).

```bash
# Agent-ready external spec -> exit 0
npx @stoplight/spectral-cli lint openapi/reconciliations.yaml \
  --ruleset governance/floqast.spectral.yaml --fail-severity error
python3 scripts/agent_readiness.py openapi/reconciliations.yaml      # 100/100 agent-ready

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
| `POSTMAN_LIVE` | variable | `true` enables the `onboard` job (onboard runs on manual dispatch only). |
| `INSIGHTS_SECURITY_APPROVED` | variable | `true` (after sign-off) enables the `insights` job. |
| `READINESS_MIN_SCORE` | variable | Optional. Set (e.g. `80`) to turn agent-readiness into a hard gate; unset = advisory. |
| `POSTMAN_MONITOR_CRON` | variable | Optional. Cloud monitor schedule for CI monitoring (default `0 */6 * * *`). |
| `POSTMAN_SYSTEM_ENV_MAP` | variable | Optional. JSON `{env-slug: system-env-id}` to associate Postman envs with team system environments. |
| `POSTMAN_INSIGHTS_PROJECT_ID` | variable | Optional. Insights project ID (`svc_*`, UI-created) enabling the agent + mock-traffic capture in the `insights` job. |

**Gating model:** governance is the **hard gate** (blockers fail the build). Agent-readiness
is **advisory by default** - it's scored and surfaced, so a governance-compliant but
"needs-work" spec still passes - unless you opt in to enforcement via `READINESS_MIN_SCORE`.

See [docs/PIPELINE.md](docs/PIPELINE.md#turning-on-the-live-postman-stages) to go live.

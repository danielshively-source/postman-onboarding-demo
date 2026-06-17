# FloQast CSE Pipeline

**Goal:** prove Postman can support FloQast's move from internal, UI-backed APIs to
external, API-first / headless, agent-ready APIs.

**In one sentence:** turn FloQast's first external-ready APIs into **governed,
discoverable, CI-enforced, agent-ready** Postman assets while proving the
onboarding effort is manageable for their existing GitHub, monorepo, and test setup.

This repo is a runnable proof of that pipeline. The governance gate runs today with
no Postman credentials; the live-Postman stages turn on with a single repo variable.

---

## How the stages map to the six jobs

| FloQast job | Where it lives | Status without Postman creds |
| --- | --- | --- |
| 1. Ingest first external-ready API batch | `openapi/`, `onboard` job (spec import + repo sync) | Spec lives in repo today; import runs when live |
| 2. Governance + linting quality gate | `governance/floqast.spectral.yaml`, `governance` job | **Runs now, blocking** |
| 3. Publish to discoverable catalog | `onboard` job (workspace link) + PAN publish | Runs when live |
| 4. CI/CD without a rewrite | this workflow + [no-rewrite matrix](#job-4--cicd-without-a-rewrite) | Demonstrated now |
| 5. Runtime visibility / session replay | `insights` job (double-gated) | Off until security sign-off |
| 6. MCP / agent-readiness | `scripts/agent_readiness.py` + [MCP section](#job-6--mcp--agent-readiness) | Scoring runs now |

### Pipeline flow (the 10 steps)

```
 1. Select candidate API        ->  openapi/core-payments-openapi.yaml
 2. Import spec                 ->  onboard job (postman-bootstrap-action)
 3. Connect source control      ->  onboard job (postman-repo-sync-action, repo link)
 4. Apply governance            ->  governance job (Spectral, Stripe-level ruleset)   [BLOCKING]
 5. Fix / document violations   ->  blocker vs warning severity + PR annotations
 6. Generate / sync collection  ->  onboard job (collections from spec)
 7. Wire into CI/CD             ->  this workflow (push to main / PR / dispatch)
 8. Publish to catalog          ->  onboard job + Private API Network
 9. Validate MCP / agent use    ->  agent_readiness.py + Postman MCP
10. Optional runtime insights   ->  insights job (after security review only)
```

The ordering is enforced by job dependencies: `onboard` `needs: governance`, and
`insights` `needs: onboard`. **No API reaches Postman unless its spec passes the gate.**

---

## Job 2 - Governance + linting (the most important success criterion)

> Sowmiya: "spec governance is going to be the most important thing. And then discovery."

- Ruleset: [`governance/floqast.spectral.yaml`](../governance/floqast.spectral.yaml),
  extending `spectral:oas` with FloQast "Stripe-level" rules.
- **Severity contract:** `error` = **blocker** (fails CI, not ready to publish);
  `warn` = **flag** (surfaced, non-blocking). This is the "classify as blocker/warning" step.
- Runs **both** places: design-time in Postman (mirror the same rules into Postman API
  Governance) and in CI/CD (this workflow). Identical feedback in both.
- Replaces inconsistent custom Swagger scripts with one centralized, enforceable standard.

What the Stripe-level ruleset enforces (selected):

| Standard | Rule(s) | Severity |
| --- | --- | --- |
| Accountable owner in catalog | `info-contact`, `floqast-info-contact-owner` | blocker |
| Self-describing operations | `operation-operationId`, `operation-description`, `floqast-operation-summary` | blocker |
| Unique, stable tool names | `operation-operationId-unique`, `floqast-operationid-camelcase` | blocker / flag |
| Discoverable grouping | `operation-tags`, `floqast-tag-description` | blocker |
| Typed success + error bodies | `floqast-success-response-schema`, `floqast-error-response-schema` | blocker |
| Auth before external exposure | `floqast-security-scheme-defined`, `floqast-global-security-applied` | blocker |
| HTTPS + versioned transport | `floqast-https-only`, `floqast-versioned-server` | blocker / flag |
| Consistent contracts | `floqast-snake-case-properties` | flag |
| Agent comprehension | `floqast-schema-property-description`, `floqast-response-examples` | flag |

Prove it locally:

```bash
# Compliant reference -> passes, exit 0
npx @stoplight/spectral-cli lint openapi/core-payments-openapi.yaml \
  --ruleset governance/floqast.spectral.yaml --fail-severity error

# Legacy internal API -> 15 blockers, exit 1
npx @stoplight/spectral-cli lint examples/non-compliant/legacy-internal-api.yaml \
  --ruleset governance/floqast.spectral.yaml --fail-severity error
```

> **Postman AI fix suggestions** (Step 5): in the Postman app, governance violations
> surface inline on the spec and Postbot can propose fixes. The CI gate and the app use
> the same rules, so a fix that turns the app green also turns CI green.

---

## Job 1 - Ingest the first external-ready API batch

The sample batch (stand-ins for FloQast's first external-ready APIs):

| Spec | Domain | Gate | Readiness |
| --- | --- | --- | --- |
| `openapi/reconciliations.yaml` | Account reconciliations | PASS | 100 (agent-ready) |
| `openapi/core-payments-openapi.yaml` | Payments (generic reference) | PASS | 100 (agent-ready) |
| `openapi/close-tasks.yaml` | Close checklist tasks | PASS | 70 (needs-work) |
| `examples/non-compliant/legacy-internal-api.yaml` | Legacy internal API | FAIL | 17.5 (ui-oriented) |

Run any of them on demand: **Actions -> FloQast API Pipeline -> Run workflow -> Spec**.
`close-tasks.yaml` deliberately passes governance but scores "needs-work" to show that
governance-compliant and agent-ready are distinct bars.

- Specs live in `openapi/` (Swagger/OpenAPI). Add one file per service in the first batch.
- The `onboard` job imports each spec into Postman Spec Hub, connects it to a workspace,
  and (via `postman-repo-sync-action`) connects it back to this GitHub repo/monorepo.
- `collection-sync-mode: refresh` + `spec-sync-mode: update` keep Postman assets aligned
  with the source-controlled definition on every push - no drift, no duplicate versions.
- This **augments** the existing GitHub Actions workflow; it does not replace it.

---

## Job 3 - Publish to a discoverable internal catalog

> Justin: "discovery" = make collections findable for internal teams **before** they build.

- The `onboard` job links the workspace and generates collections - the catalog foundation.
- Publish the linked collection/workspace to the **Private API Network (PAN)** so it is
  searchable internally. Carry ownership metadata from `info.contact` (enforced by governance)
  plus links to repo, collections, docs, and environments.
- Outcome: a FloQast engineer searches Postman first, finds the existing API + docs + tests +
  owner, and avoids rebuilding it. Same catalog becomes the trusted source for agents.

---

## Job 4 - CI/CD without a rewrite

> Bhavesh's concern: do we have to recreate existing integration tests as Postman collections?
> **No.** Here is the decision matrix.

| FloQast asset | Recommendation | Where it runs |
| --- | --- | --- |
| Existing coded integration tests (Jest/Go/etc.) | **Keep as-is** | Existing GitHub Actions |
| OpenAPI/Swagger specs | Govern in CI + import to Postman | This workflow |
| Contract / smoke checks against the spec | Generate as Postman collections | Postman CLI / Newman |
| Cross-service / scenario API tests | Optionally author in Postman | Postman CLI in CI |
| Test results / health | Surface in Postman + catalog | CLI publishes back |

- **Integrate directly from GitHub Actions:** governance, spec import, collection sync,
  Postman CLI runs - all callable from the existing pipeline.
- **Becomes a Postman collection (only where it adds value):** spec-derived contract/smoke
  suites and agent-facing scenario tests. Existing unit/integration tests stay put.
- **Newman / Postman CLI:** runs the generated collections in CI and (with creds) publishes
  JUnit + results back to the workspace/catalog.
- **Effort:** ~1 spec file + this workflow per service. Monorepos add one `openapi/*.yaml`
  entry and one matrix row per service - no per-service rewrite.

Start with **one representative FloQast service** (mirrors `core-payments` here), prove the
loop, then template it across the monorepo.

---

## Job 5 - Runtime visibility / session replay (security-gated)

Secondary to governance/discovery, and **off by default**. The `insights` job requires
**two** repo variables: `POSTMAN_LIVE=true` **and** `INSIGHTS_SECURITY_APPROVED=true`.

### Privacy / security checkpoint (must clear before enabling)

| Question (raised by Bhavesh) | Must answer before turning on |
| --- | --- |
| How is the agent/sidecar deployed? | Insights agent runs as a sidecar/daemon next to the service |
| Does it work on **ECS** (no Kubernetes)? | Validate ECS sidecar deployment - FloQast is not on k8s |
| What data is captured? | Endpoints, status, latency, shapes - confirm scope |
| Are request params / customer data captured? | Define redaction/sampling; exclude PII fields |
| How is production data excluded/protected? | Drop/obfuscate sensitive fields at the agent before egress |
| How does this differ from Grafana/CloudWatch/Coralogix? | Position as API-shape + replay, not infra metrics |
| What is required from FloQast infra teams? | Sidecar deployment + egress allow-list |

> Do **not** enable against production-like traffic until FloQast security signs off on the
> data-handling answers above. Start with a non-production service.

---

## Job 6 - MCP / agent-readiness

> Raaj: can Postman score whether an API is UI-oriented vs agent-ready?
> Bhavesh: can Postman validate/test MCP server tools?

- **Readiness scoring:** [`scripts/agent_readiness.py`](../scripts/agent_readiness.py) scores
  each spec 0-100 and labels it `agent-ready` / `needs-work` / `ui-oriented`. Criteria are the
  things agents need to act without loading the whole spec: unique operationIds, summaries +
  descriptions, typed success/error schemas, documented params, applied security, and examples.
  The `governance` job runs it with `--min-score 80`.
- **REST -> MCP candidates:** an API that passes governance + scores agent-ready is a clean
  candidate for MCP exposure (stable tool names from camelCase operationIds, typed args/results,
  examples for grounding).
- **Test MCP tools in Postman:** import/generate the MCP server, then exercise tool calls in
  Postman like any request; assert on responses.
- **Claude / Postman MCP:** point an MCP-capable agent at the Postman MCP server so it can
  retrieve only the relevant API context (the cataloged, governed collection) instead of a
  giant raw spec - Postman becomes the system of record agents trust.

---

## Success criteria (what this proves)

- [x] Take an existing spec into Postman with minimal friction (1 file + 1 workflow).
- [x] Enforce "Stripe-level" standards automatically (Spectral ruleset, blocking).
- [x] Run governance in CI/CD (the `governance` job).
- [ ] Avoid duplicate work via internal discovery (PAN publish - needs live creds).
- [x] Keep Postman assets aligned with GitHub (refresh/update sync modes).
- [x] Understand migration effort for existing tests (no-rewrite matrix).
- [x] Validate APIs + MCP tools for agentic consumption (readiness score + MCP track).
- [x] Evaluate runtime visibility without compromising customer data (security-gated job).

---

## Turning on the live-Postman stages

1. Set repo secret `POSTMAN_API_KEY` to a **valid** service-account PMAK (US region).
2. Set repo variable `POSTMAN_LIVE=true`.
3. (Optional, after security sign-off) set `INSIGHTS_SECURITY_APPROVED=true`.

```bash
gh secret set POSTMAN_API_KEY            # paste a valid PMAK
gh variable set POSTMAN_LIVE --body true
gh workflow run "FloQast API Pipeline"
```

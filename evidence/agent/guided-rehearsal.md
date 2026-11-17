# Codex model-guided rehearsal

The rehearsal demonstrates a real Codex 0.166.0 model choosing and executing
openSoom read-only MCP calls. It does **not** demonstrate complete guided
onboarding: two setup-skill checks were omitted and the final explanation was
truncated at the configured output limit. Keep the corresponding acceptance
target open.

## Starting state and boundaries

- A maintainer had installed the application, started the virtual runtime and
  activated the approved profiles. Those actions are not model accomplishments.
- The test created a fresh project-local Codex profile and an empty temporary
  workspace, installed the local plugin using the existing installer, selected
  its discovered `opensoom-setup` skill and submitted a Korean natural-language
  setup/diagnosis request. The normal Codex profile was untouched.
- The model ran through the actual Codex app-server `thread/start` and
  `turn/start` methods. The harness never directly called operational MCP tools.
  Its final independent service-run retrieval is a separate verification.
- Only `doctor`, `prepare_setup`, `discover`, `read_group` and `read_evidence`
  were offered. Normal per-call approvals checked the registered plugin,
  started tool call, exact server, arguments, approval schema and facility scope.
  Approvals were accepted once, never persisted. Other approval requests were
  rejected. Nine zero-inference boundary checks passed.
- The sole inference destination was `https://api.openai.com/v1/responses` with
  `gpt-5-mini`, synthetic facility data, no provider retries, a 45-second request
  timeout, 180-second turn timeout and 1,024 maximum output tokens. The proxy
  reserved each request in the existing shared budget before forwarding it.
- The entire guided-rehearsal scope, including failed attempts, was six provider
  requests and at most 50,000 charged tokens. It used six requests / 20,385
  tokens. The shared batch remains 100 requests / 250,000 tokens and ended at
  66 requests / 218,430 tokens, with no pending reservation.

## Observed outcome

The first live attempt used two requests. The model selected `doctor`, but the
initial harness rejected the standard MCP approval request. The failed result
is preserved in `guided-first-live-approval-denied.json`.

Two zero-inference protocol fixtures then captured the actual host approval
request and verified its normal one-time acceptance. They are explicitly
synthetic model-response fixtures and are not live-model evidence.

The final live attempt used four requests. The model selected and completed
`doctor`, `discover(facility_id="learning-b")` and
`read_evidence(facility_id="learning-b")`. Its facility calls shared service run
`mcp-66f29931a3bb`, which the verifier retrieved independently. The returned
records include real oneM2M discovery and request IDs. The model's Korean output
correctly repeated the simulated classroom readings: PM2.5 62 µg/m³, CO₂
1,450 ppm, airflow 200 m³/h, and an unresolved critical incident.

The model did not select `prepare_setup` or `read_group`. Its final response
exceeded 1,024 output tokens, so Codex reported a failed turn with
`max_output_tokens`; the captured Korean text is partial output. It must not be
presented as a completed user response or complete setup-skill execution. No
role, profile, scenario or actuator changes occurred in this rehearsal.

## Reproduction and evidence

From the project root, after normal runtime setup and local plugin prerequisites:

```sh
.venv/bin/python scripts/codex_guided_rehearsal.py --output evidence/agent/guided-dry-capture.json
.venv/bin/python scripts/codex_guided_rehearsal.py --protocol-fixture --output evidence/agent/guided-protocol-approved.json
```

The default captures the actual Codex request without forwarding it. The
explicit protocol fixture replays a synthetic `doctor` request to validate host
approval, and cannot be combined with `--live`.

The historical live command was:

```sh
.venv/bin/python scripts/codex_guided_rehearsal.py --live --output evidence/agent/guided-live.json
```

The fixed six-request rehearsal allowance is now exhausted. The script must
reject further inference under this scope; do not delete its shared database,
change run prefixes, or reset the allowance to repeat the test. A future
explicitly bounded task can consider a shorter requested Korean answer and a
larger output cap while preserving the existing shared batch limits.

`guided-checkpoint.json` binds the script and JSON evidence hashes.
`guided-correlation.json` records the independently retrieved service run and
the precise partial-result limitations. `guided-approval-scope-checks.json`
records nine host approval boundary checks. All child app-server and proxy
processes stopped; the existing application/CSE/broker processes were preserved.

## Protocol references

Configuration and app-server fields were checked against the installed CLI's
generated JSON schemas and the official documentation:

- [Codex configuration reference](https://developers.openai.com/codex/config-reference/)
- [Codex app-server protocol](https://developers.openai.com/codex/app-server/)
- [Responses function calling](https://developers.openai.com/api/docs/guides/function-calling)

The zero-inference capture confirmed this installed version's exact
`mcpServer/elicitation/request` form with `codex_approval_kind="mcp_tool_call"`.
The accepted response was `{"action":"accept","content":{}}`, with no
persistence metadata or global policy change.

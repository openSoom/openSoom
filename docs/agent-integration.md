# Codex plugin and real-model runner

openSoom exposes one operational tool boundary. The Codex plugin packages setup and operation skills with an MCP server. The standalone runner connects to that same MCP server over stdio, gives its schemas to a real model, executes model-generated tool calls, and records the service's independent outcome check. Both paths reach the running openSoom service and its actual oneM2M CSE.

The demonstration's physical sensors, airflow and damper are simulated. An API response, CSE write or device acknowledgement alone is not a recovered incident. Recovery requires an acknowledged command and later CSE observations satisfying the activated facility profile. None of this establishes certified ventilation or a health outcome.

## Start and connect

Complete the repository's [runtime setup](../README.md) first. The supported development environment uses Python 3.12, the pinned `uv.lock`, MCP Python SDK 2.3.0 and Codex CLI 0.166.0. `uv` and `codex` must be on the host's PATH. The plugin installer uses the checkout's pinned environment without downloading dependencies when a tool starts.

From the checkout, prepare and verify plugin installation in a separate Codex profile:

```sh
uv run --no-sync python scripts/agent_install_plugin.py --install
uv run --no-sync python scripts/agent_codex_check.py
```

The first command uses `.runtime/codex-plugin-check`; the acceptance check creates a fresh `.runtime/codex-acceptance-*` profile. Neither modifies the user's ordinary Codex profile. Installing into the Codex profile you actually use is an explicit separate command:

```sh
uv run --no-sync python scripts/agent_install_plugin.py --install --current-host
```

Open a new Codex chat after installation, select openSoom, and ask **“openSoom 가상 시설을 연결하고 현재 상태를 설명해주세요.”** The onboarding skill calls `doctor`, explains runtime/CSE readiness separately, validates a supplied profile, discovers accessible equipment and reads its current evidence. English works too. A missing service or credential produces a setup instruction; the operator is never asked to paste a key into chat.

To remove an installation from the current Codex profile, use `codex plugin remove opensoom@opensoom-local` and, if no longer needed, `codex plugin marketplace remove opensoom-local`. This removes the plugin connection, not facility data or the live-test budget.

Plugin registration does not start the service. Use the root CLI for lifecycle operations:

```sh
uv run --no-sync opensoom doctor
uv run --no-sync opensoom stop
uv run --no-sync opensoom start
```

`restart` is also available. `cleanup` intentionally removes the openSoom operational state and scoped service credentials; consult the README before using it. It retains the shared LLM budget. Never remove or recreate the budget database to obtain more test allowance.

The CLI keeps the port and an allowlist of runtime settings in `.runtime/service-config.json`, separately from the live PID record. After `start --secure`, later `doctor`, `stop`, `start`, `restart`, and foreground `serve` reuse that configuration without repeating environment variables. Explicit runtime environment settings and `--port` can override it when starting; provider keys and service tokens are never persisted there. Older process records containing runtime settings are migrated before stopping. A stop timeout or unrelated PID leaves the record intact and aborts restart/cleanup; only a confirmed exited service permits cleanup. Configuration, CSE state and the LLM budget survive cleanup.

For a reproducible clean application lifecycle check, run:

```sh
uv run --no-sync python scripts/release_reproduce.py
```

This creates a separate source copy, installs two new Python environments (dependency caches may be reused), starts a new certificate-verified HTTPS CSE on 8643 and an application on 8179, then checks diagnosis, deterministic recovery, stop/start without repeated settings, restart, pending-command preservation through timeout, and cleanup. It leaves the ordinary 8090 service alone and stops its own service/CSE. [Final lifecycle evidence](../evidence/release/final-clean-lifecycle.json) records the outcomes; the [initial failed copier attempt](../evidence/release/clean-lifecycle-initial-failed.json) is retained separately. The synthetic budget-preservation sentinel performs no model request. This check does not add a desktop UI or MQTT acceptance claim.

## Tool and permission contract

| Tool | Purpose |
| --- | --- |
| `doctor` | Explain service/CSE readiness without exposing credentials. |
| `prepare_setup` | Inspect a bundled facility profile and its activation requirements. |
| `apply_setup` | Request profile activation; the service requires its administrator identity. |
| `discover` | Discover accessible facility resources through oneM2M. |
| `read_group` | Read the native CSE group/fan-out result, preserving failures. |
| `read_evidence` | Inspect observations, freshness, incidents and commands. |
| `request_action` | Request a scoped, profile-authorized damper or maintenance action. |
| `verify_result` | Check command acknowledgement and subsequent observations. |

The MCP process uses the operator token in `.runtime/service-credentials.json`, or an explicitly supplied `OPENSOOM_SERVICE_TOKEN`. It never changes identity when a tool is denied. Roles, facilities, profile permissions, schema validation, idempotency and data freshness are enforced by the service. The live runner exposes only the six operational tools; it does not offer setup/profile activation to the model.

`request_id` identifies one intended action and is reused only when retrying the same arguments within the same run. Prefix it with the current returned `run_id`; historical commands cannot establish a new incident's recovery. `verify_result` must return all of `complete: true`, `ack: true`, and `observed_result: "recovered"` before the agent reports recovery. Pending, timed-out, stale, denied and observed non-recovery outcomes remain distinct. The service owns run/incident state and correlates `X-OpenSoom-Run-ID` with actual tool calls, CSE request IDs, command IDs and acknowledgements. The standalone runner creates its explicit run. A Codex MCP connection lazily creates a separate `mcp_host` run for each accessed facility, keeps its identity across tool calls, and returns the ID. Creating a read-only observer run does not grant control privileges.

`read_evidence.evidence_scope` states the limits of its evidence. Incidents span
the facility's stored runs, but `commands` contains only the latest ten commands
for the stated run. An empty list cannot establish that no earlier action or
ACK occurred. Incident `recovery_count` counts consecutive qualifying healthy
post-ACK observations and resets for a non-nominal observation; it does not
count attempts. The returned contract gives its unit, required sample count
and history scope so clients can preserve that distinction.

For real equipment, observation and diagnosis remain the default until a facility configuration authorizes controls. The bundled virtual profiles support preauthorized simulated actions. Changing the MCP identity is not a remedy for an operator denial.

## Account-free fixture

```sh
uv run --no-sync python -m opensoom.llm_runner \
  --mode fixture --facility food-a --scenario exhaust_fault \
  --expect recovered --prepare-scenario
```

`--prepare-scenario` sets virtual input conditions with scripted automatic action disabled. The fixture then invokes the actual MCP and CSE tool path deterministically. Its result is `PASS_FIXTURE`, never live-model evidence. Verification polls are bounded and allow the virtual adapter plus two later samples to arrive; repeatedly reading one sample does not count twice.

## Actual LLM API execution

Supply the provider key through the process environment or a secret manager, outside source files and prompts. For the default OpenAI endpoint, the runner uses `OPENAI_API_KEY`. The default model is `gpt-5-mini`; its availability was checked through the public model API before the first inference test. It is separate from the internal GPT-6.1 Sol rubric reviewers.

```sh
uv run --no-sync python -m opensoom.llm_runner \
  --mode live --model gpt-5-mini --facility food-a \
  --scenario exhaust_fault --expect recovered --prepare-scenario

uv run --no-sync python -m opensoom.llm_runner \
  --mode live --model gpt-5-mini --facility food-a \
  --scenario stale --expect unresolved --prepare-scenario
```

The model receives actual MCP schemas and results, decides tool calls, and produces a structured final report. The evaluator requires observed evidence and a matching report. The service independently checks its own recorded tools and command state before accepting a pass. `PASS_HOSTED_LLM_E2E` means the requested test expectation was verified; for a negative scenario the facility remains unresolved. It never means a failed physical condition recovered.

There is no fallback from a failed API call to a fixture. A missing key, timeout, exhausted budget or unsupported endpoint results in `FAIL` or `BLOCKED`, with a sanitized reason. API connectivity or a text-only answer cannot pass.

The configurable provider interface is a Responses-compatible endpoint:

| Environment setting | Meaning |
| --- | --- |
| `OPENSOOM_LLM_BASE_URL` | Base URL ending before `/responses`; defaults to `https://api.openai.com/v1`. |
| `OPENSOOM_LLM_API_KEY` | Explicit key for that endpoint. |
| `OPENSOOM_LLM_MODEL` | Default model ID; `--model` overrides it. |
| `OPENSOOM_SERVICE_URL` | openSoom service URL; defaults to local port 8090. |
| `OPENSOOM_PROJECT_DIR` | Checkout containing profiles, runtime credentials and budget configuration. |

Remote endpoints require HTTPS. Plain HTTP is limited to localhost. A custom provider never receives the OpenAI environment key implicitly. A local provider must support the used Responses function-calling and structured-output fields; compatibility and model quality require a separate executed test. The local-provider outcome label is `PASS_LOCAL_LLM_E2E`; no local-model pass is claimed by the hosted tests.

The provider key is not inherited by the MCP subprocess. Ordinary tool results, public traces and plugin manifests do not include service tokens or CSE credentials.

## Bounded shared use

`config/live-test-budget.json` defines the authorized batch: 100 inference requests and 250,000 combined input/output tokens across runs, workers and restarts. Each run has at most 12 model steps and 12 tool calls, responses are capped at 4,096 output tokens, network requests time out after 45 seconds, and a failed step gets at most two total attempts. Retries consume the shared batch.

`.runtime/llm-budget.sqlite` reserves calls and conservative token bounds atomically before network access. Known provider usage settles the reservation. Unknown usage, interrupted requests and unreturned requests keep their full reservation charged. Reopening the database cannot change its limits, and an unexpected usage discrepancy blocks further requests. The batch is separate from any Codex Goal token budget.

## Evidence and current limits

The [agent evidence directory](../evidence/agent/) contains sanitized traces, exact model response IDs/usage, generated tool arguments and results, service validation, and Codex host checks. Private runtime diagnostics remain under ignored `.runtime/`.

The [evidence index](../evidence/agent/index.json) identifies the final accepted implementation checks and retains rejected or superseded attempts. The current-source accepted checks and retained historical evidence are separated below:

| Check | Captured evidence |
| --- | --- |
| Current-source real model recovers after ACK and later observations | [Release recovery](../evidence/agent/release-live-recovery.json) |
| Historical real-model non-recovery after ACK and two deficient samples | [Historical non-recovery](../evidence/agent/secure-live-no-recovery.json); latest code has a separate deterministic actual-CSE check |
| Current-source model attempts control, server rejects stale evidence before CSE write, model reports unresolved | [Release stale-data run](../evidence/agent/release-live-stale.json) |
| Fresh Codex plugin installation, six actual host tool calls, administrator denial and persistent run correlation | [Release Codex host check](../evidence/agent/release-codex-host.json) |

[Correlated protocol records](../evidence/agent/release-protocol-correlation.json) match 33 CSE request IDs from those checks. MCP uses local stdio and the service uses local HTTP; HTTPS and native MQTT/TLS are the distinct service/device-to-CSE bindings. Their separate [HTTPS](../evidence/runtime/cse-https-smoke.json) and [MQTT/TLS](../evidence/runtime/cse-mqtt-tls-smoke.json) checks establish those bindings.

The clean-host test installs the actual plugin into Codex CLI 0.166.0, opens an ephemeral app-server session, discovers its MCP server and calls tools through the host. It does not run a Codex model turn, change normal authentication/security settings, or establish a separately tested desktop UI flow. The standalone API tests separately establish real-model operation. Human first-use usability and other agent hosts require their own evidence.

Separate instrumented Codex model turns now also have preserved evidence. In
the [guided diagnosis](../evidence/agent/guided-rehearsal.md), Codex chose and
executed `doctor`, `discover` and `read_evidence`. In the
[configuration check](../evidence/agent/guided-config-report.md), it chose
`prepare_setup` and `read_group`; the native group returned three members.
Both cases reached their fixed limits before delivering a completed final
explanation, so neither is a passed end-to-end onboarding conversation.
The runtime and profiles had been installed and activated by the maintainer;
these checks do not establish autonomous installation or administrator access.

A distinct [recorded-results explanation](../evidence/agent/guided-explanation-report.md)
completed in an actual Codex turn without operational tools. Its original
Korean text and source mappings are retained. Independent factual acceptance
is separate: the model inferred that no recovery had been attempted from a
zero recovery-sample counter, which does not support that conclusion. A
completed response alone is therefore not the complete onboarding gate.
These are separate chats, not a reconstructed uninterrupted conversation.

The later [measurement-complete validation](../evidence/agent/units-live.json)
restores whole observation objects, including units, timestamps, source and
quality. Its actual Codex response preserves the recorded quantities and prior
ACK/non-recovery history. Both provider and host completed normally. The raw
harness still records `INCOMPLETE_CAPTURED_RECORD_EXPLANATION`: a preface plus
six numbered sentences exceeded its six-sentence format check. This status
and all earlier factual failures remain unchanged; independent reviewers must
assess the stage's functional outcome separately from that format deviation.
The [input mapping](../evidence/agent/units-input-map.json) retains every chosen
fact and the restored measurement objects without fabricating chat history.

Early failed attempts are retained: the first fixture ended before recovery samples arrived; the first portable plugin used an unsupported absolute executable command. Both were corrected and retested. The first no-recovery live run observed a pre-ACK state and is weak negative evidence. A later run exposed reuse of a previous incident's idempotency key; current-run checks now reject it. The first release recapture also failed because the model skipped the required read_evidence step despite eventual device recovery. That failure is retained; a later run satisfied the full workflow. Acceptance uses the explicitly indexed current-source traces above. Independent rubric review remains separate from these implementation checks.

## Primary references

- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins): portable manifests, fixed component paths and onboarding skills.
- [MCP Python SDK](https://py.sdk.modelcontextprotocol.io/) and [client transports](https://py.sdk.modelcontextprotocol.io/client/transports/): pinned SDK server/client integration.
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling): model-selected function requests and tool outputs.
- [GPT-5 mini model reference](https://developers.openai.com/api/docs/models/gpt-5-mini): the public model used by the hosted tests.

The host acceptance script uses the app-server schemas generated by the installed Codex 0.166.0 CLI. Plugin format validation and successful installation are recorded separately from successful host tool execution.

The [setup-role check](../evidence/agent/setup-acceptance.json) separately verifies operator preparation, operator activation denial, unknown-profile rejection, and repeated successful activation through the preconfigured administrator identity. It does not give the operational model administrator authority.

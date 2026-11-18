# Implementation goals and acceptance evidence

**Historical first-release plan.** Its execution closed before the six-team release cycle. Use the [next release plan](release-goal.ko.md), [new checkpoint](release-goal-state.json) and [current reviewer charter](review/review-charter.json) for new work. Preparing a document does not complete its stage. The execution ledger is [execution-state.json](execution-state.json). The accepted product boundaries remain in [product-contract.json](product-contract.json).

## Outcome and scope

Produce a reproducible openSoom hackathon release: a reusable facility operations core, actual oneM2M integration, virtual equipment, a usable Codex plugin, a standalone real-LLM API runner, a dashboard, and an English submission package. School kitchens are one example of food-production and other ventilation-required facilities.

The product connects observations to diagnosis, authorized action, acknowledgement, outcome verification and maintenance. Consistent operations do not imply identical ventilation thresholds. Physical measurements and actuator responses are simulated; CSE, MCP and model execution must have their own real execution evidence.

Repository publication to `openSoom/openSoom` through the user-selected `github-personal` identity is authorized. The autonomous release goal includes a submission-ready Hackster draft, video artifact and presentation material. Publishing to Hackster/video services, contacting judges or posting to Discord is outside this goal unless explicitly authorized separately. Record those handoff actions without blocking authorized implementation.

## Stable requirements and flexible choices

These outcomes cannot be silently removed to finish sooner:

- An actual CSE-backed observation → incident → authorized action → device ACK → subsequent observation flow, including unsuccessful outcomes.
- Two facility profiles and two differently formatted vendor adapters using unchanged core and tool code.
- Native oneM2M discovery, subscriptions and group/fan-out use; separate application identities and enforced access policies; verified secure transports and appropriate protocol use.
- Guided Codex onboarding and operations, plus a standalone real LLM API flow using the same MCP/service path and durable run state.
- An account-free deterministic demonstration, reproducible installation/lifecycle instructions, and clear simulation labels.
- A coherent distributed facility demonstration, a useful dashboard, and evidence-based repository/article/video/presentation material.
- Independent rubric reviews, traceable findings, and truthful limitations.

The main agent may change language/framework, internal process layout, tool names, task size, work order, implementation techniques and proposed file layout. Preserve acceptance outcomes. Record a reason and affected gate IDs for material changes; re-review affected criteria. A gate cannot be relaxed merely because it failed. A technically equivalent check may replace a check after independent review, with both old and new checks recorded.

MEC hosting/services and CSE handover are conditional extensions investigated early. Advanced SDT/semantic modeling is a high-value interoperability target with a separate conditional gate; basic FCNT/discovery and adapter meaning/unit validation are required. Federated learning and geolocation remain deferred until their product need and executable path exist. All 17 criteria remain visible; a deferral is not official N/A or earned credit. Track applicability, weights and exact submission cutoff remain unverified. The working submission date is 2026-11-20; schedule decisions use Asia/Seoul and do not invent a midnight cutoff.

## Stage overview

| Stage | Outcome | Dependencies | Review |
| --- | --- | --- | --- |
| 0 | Executable scenario specification, selected runtime and implementation skeleton | Existing product contract and rubric | All four teams |
| 1 | One real end-to-end service flow with failure evidence | Stage 0 contracts | All four teams at first CSE flow |
| 2 | Standards use and reusable facility/vendor integration | Stage 1 path | Teams 1 and 3; Team 2 adoption check |
| 3 | Codex onboarding and actual LLM execution | Stable tools from stages 1–2; packaging work may start earlier | All four teams |
| 4 | Distributed facility operation and justified extensions | Stage 2 resource/identity model; feasibility starts in stage 0 | Teams 1, 3 and 4 |
| 5 | Clear dashboard and verified demonstration media | A basic screen starts in stage 1; final capture uses verified stages 1–4 | Teams 2 and 3 |
| 6 | Reproducible release and submission-ready package | Required gates and documented extension dispositions | All four teams |

This is a dependency map, not a requirement to work serially. UI scaffolding, documentation, plugin packaging and bounded external feasibility checks can run in parallel with core implementation. Never wait on an optional endpoint while independent core work is available.

## Stage 0 — Specify and scaffold the first runnable scenario

**Objective:** turn the brief into inputs, expected behavior and a runnable development starting point, without spending the whole run on architecture documents.

Work:

- Define one multi-zone food-production example, generic facility/zone/asset/capability identities, relevant measurements, units, observed/received timestamps and freshness rules. Profile values are simulation parameters, not certified operating guidance.
- Specify normal operation, insufficient exhaust despite a running fan, missing/stale observations, an unacknowledged action, maintenance and verified recovery. Define expected state transitions, permitted actions and non-recovery behavior before selecting graphs.
- Specify adapter, facility-profile, command, incident and shared MCP contracts; command identity, expiry, idempotency and per-device outcomes must be explicit. Choose a minimal SDT/semantic mapping scope to validate later.
- Select and pin a real CSE implementation and the runtime based on available tools, protocol/security support, reproducibility and licensing. ACME is a candidate, not an already-verified dependency. Prefer a small number of processes and a project-local environment. Record a bounded alternative when Docker or another runtime is unavailable.
- Create the initial source/configuration/test layout, schema/sample-profile validation and startup/preflight skeleton. Proposed directories are `src/`, `profiles/`, `adapters/`, `scenarios/`, `tests/`, `deploy/`, `plugin/` and `evidence/`; adjust to the chosen stack.
- Check project-scoped provider configuration, current Codex integration path and available MEC host/service access. Record presence/readiness only, without exposing secrets. Check access and image-deployment permissions before investing in an external architecture.
- Before any live model tests, set a finite shared test-batch request/token allowance as well as per-run limits. All workers, retries and restarts use the same persistent accounting record; reserve capacity before calls so concurrency cannot exceed it. Do not reset or automatically increase the allowance after exhaustion. This product-test allowance is separate from the Goal tool's token budget, which the user has not specified.

Completion gates:

- **S0-G1:** versioned scenario specification has reproducible inputs, observable expected results and failure conditions for all cases above; state/profile/adapter contracts are concrete enough to implement.
- **S0-G2:** runtime/CSE versions, license, start command and first actual-CSE smoke-check procedure are recorded. Local schema/sample checks run successfully; a prerequisite check reports useful diagnostics. CSE smoke execution belongs to stage 1 and is not claimed here.
- **S0-G3:** feasibility record identifies real LLM, Codex and MEC readiness, attempts, known blockers and independent next actions. The live-test batch has explicit shared request/token limits, accounting/reservation location and per-run bounds before execution. An unavailable external service does not fail this planning gate, but cannot satisfy its later execution gate.
- **S0-G4:** all four teams review the same snapshot; the main agent records dispositions and fixes any stage-0 completion blocker. Product-code findings remain open until implemented and verified.

## Stage 1 — Complete the actual service loop

**Objective:** a virtual facility produces observations in a real CSE; a service diagnoses and handles an incident, then checks what happened.

Work: start the CSE and virtual device adapter; create real resources and subscriptions; run the policy/incident path; send a scoped command through CSE resources; receive per-device acknowledgement and later observations. Persist run and incident state. Add a basic dashboard showing current state and the event timeline.

Completion gates:

- **S1-G1:** repeatable start/reset instructions produce actual CSE requests and resource changes for normal → anomaly → allowed action → ACK → verified recovery, with `runId`, oneM2M request IDs, command IDs and timestamps.
- **S1-G2:** stale/missing evidence, absent ACK and no recovery leave an explicit unresolved/failed outcome; a successful CSE write alone never closes the incident. Repeating a command does not create a second unintended action.
- **S1-G3:** service restart preserves the incident/run and can inspect or resume a pending outcome; the basic screen agrees with recorded state and labels simulated measurements.
- **S1-G4:** all four teams review the first real CSE evidence; relevant corrections receive independent verification. No script/mock response is substituted for actual CSE execution.

## Stage 2 — Prove reuse and native oneM2M behavior

**Objective:** the same applications work across facilities and vendors, with oneM2M performing common service functions.

Work: add a second facility profile and vendor adapter; validate field/unit/capability mappings; implement native discovery, subscriptions and group/fan-out; use diagnostic, operations and maintenance application identities with distinct permissions. Implement native MQTT/TLS and HTTPS where appropriate, with a documented reason for each. Verify the selected SDT or semantic mapping against the pinned specification.

Completion gates:

- **S2-G1:** two profiles and two vendor formats use identical core/tool code; a replacement adapter preserves application behavior. Both independent applications and adapter mappings are visible in the source/resource map.
- **S2-G2:** native discovery queries, subscription notifications and group `/fopt` traces show actual application use, including per-member partial failure. Device ACK remains distinct from group success.
- **S2-G3:** secure protocol traces and both allowed and unprivileged denied ACP requests are captured; wrong-facility, out-of-scope and stale-evidence actions fail at the appropriate server/CSE boundary. Native MQTT evidence reaches the CSE binding rather than only an HTTP bridge.
- **S2-G4:** required FCNT, discovery and adapter meaning/unit mappings pass validation. Record the specification version, model identifiers, properties, data types and units, plus actual discovery queries and application use. These checks support only the evidenced interoperability level.
- **S2-G5, conditional:** prioritize a useful minimal SDT or semantic model, recording an adopt/defer decision, rationale and independent review. If adopted, validate the actual model and application use against the selected specification; failure keeps this extension incomplete until fixed or explicitly deferred with its history retained. A deferred advanced mapping does not block the required FCNT gate and does not establish Expert interoperability.

## Stage 3 — Make the service usable through Codex and a real model

**Objective:** a nontechnical user can install, configure, diagnose and recover through the plugin; an actual model can execute the shared tool workflow autonomously in the preauthorized virtual scenario.

Work: package guided workflows and MCP access; implement prerequisite checking, idempotent setup, discovery, evidence retrieval, action requests and outcome verification. The server owns identities, permissions and durable run state. Implement a configurable hosted/local model API runner with tool schema validation, step/token limits, timeouts, bounded retries and redacted traces. Keep setup/profile activation privileges separate from the operational model's privileges.

Completion gates:

- **S3-G1:** a fresh supported Codex environment follows public instructions without editing application source; separately demonstrate plugin registration, MCP connection, runtime/CSE readiness, guided setup, diagnosis, stop/restart and cleanup. Record OS, Codex version, plugin revision, prerequisites, relevant global configuration, absence of prior openSoom configuration and every additional manual action. Do not modify unrelated user settings to manufacture a clean environment. Packaging or a standalone MCP test alone is not a Codex-host pass.
- **S3-G2:** the deterministic, account-free scenario runs and is labeled `PASS_FIXTURE`; a separate real hosted or local inference API run produces model-generated tool calls through MCP/service/CSE and independently verified outcomes (`PASS_HOSTED_LLM_E2E` or `PASS_LOCAL_LLM_E2E`). Mere API connectivity and fixture fallback cannot pass this gate.
- **S3-G3:** exercise malformed tool arguments, timeout, duplicate calls, partial failure and restart; state and scope stay correct. Reject attempts to change another facility, expand permissions or use stale evidence; no credentials appear in committed examples, ordinary tool results, model prompts or recorded public traces. In addition to deterministic failure tests, an actual model plus actual CSE must handle at least one stale-evidence, denied-action or non-recovery case: the final report must agree with the unresolved/denied state and must not fabricate success or increase permissions. Verify that two workers share the live-test allowance, reservations prevent overruns, usage survives restart and exhaustion is never a live pass.
- **S3-G4:** all four teams review the same onboarding and model evidence. A developer conducting the setup rehearsal cannot conceal prerequisites or perform the model's operational decisions manually.

If credentials or host interaction are unavailable, finish the runner/plugin and all independent tests, mark the affected execution gate `blocked_external`, and continue other stages. Actual-model and Codex-host validation remain required; they cannot be silently waived or treated as goal completion.

## Stage 4 — Demonstrate distributed operation and evaluate extensions

**Objective:** local facility operation and a central operator share appropriate resources without making the simple installation unnecessarily complex.

Work: implement a two-facility demonstration, normally two MN-CSEs and a central IN-CSE, with selective resource sharing, native remote operations and appropriate ACP. Preserve a simple single-facility startup path. Evaluate maintenance/availability-driven CSE handover, actual MEC deployment and non-location MEC services using the stage-0 feasibility findings.

Completion gates:

- **S4-G1:** independently running CSEs register/connect and demonstrate intended cross-facility discovery/resource sharing and central operations with explicit identities and permissions. Record topology, remote requests and one unauthorized cross-scope case; a diagram alone is insufficient.
- **S4-G2:** losing the central connection leaves the defined local observation/policy path operational; reconnection makes state freshness and gaps visible. Define local/central action authority and reconciliation rules. Demonstrate disconnection → local action/ACK → delayed expired central command → reconnection: reject the expired command, avoid duplicate actuation and preserve current incident state. Report outage/recovery and duplicate/loss behavior. This proves only the implemented continuity behavior, not serving-CSE handover.
- **S4-G3:** record a reviewed adopt/defer decision for each of handover, MEC deployment, MEC services, FL and geolocation, using product need, simpler alternative, available environment, expected benefit and verification cost. No default exclusion of MEC/handover without investigation. Missing platform access is a condition, not a score.
- **S4-G4, conditional:** for each adopted extension, define and pass separately identified gates before claiming it: handover restores identity/state/subscriptions/ACP and measures interruption/loss; MEC deployment identifies actual hosting/registration; MEC service use connects through oneM2M/IPE and changes application behavior; FL and location meet their own original descriptors. Track each extension's criterion, decision/history, rationale, gate IDs, environment, evidence and review reference in the execution state. An adopted but incomplete extension blocks goal completion. Local mocks remain labeled. A failed extension may be deferred with independent rationale and removed from release claims, preserving its previous adoption/failure history; the required distributed core remains.

## Stage 5 — Make operation and evidence understandable

**Objective:** someone unfamiliar with the implementation can understand the facility problem, agent reasoning, equipment response and oneM2M contribution.

Work: refine the dashboard and facility visualization; show zone state, freshness, incident timeline, action/ACK/outcome and operator next steps. Begin the storyboard early and use verified runtime captures in the final demo. AI-created illustrations may explain the facility, while actual service screens/traces establish software behavior.

Completion gates:

- **S5-G1:** reviewers inspect the rendered dashboard in normal, anomaly, missing-data and unsuccessful-action states; labels and values match the selected run. The maintainer requested a further visualization pass: include a state-driven Three.js facility view with accessible text/2D fallback, reduced motion and clear illustrative-airflow labels. Do not present an invented airflow/health-improvement curve as measured evidence.
- **S5-G2:** produce a playable demo/promotional video with English narration or captions, readable scenes and clear virtual-device labels; include the problem, agent operation, oneM2M behavior, result verification and reuse evidence. Verify playback, text legibility and factual alignment against the actual run.
- **S5-G3:** preserve the reproducible capture path, storyboard/script and asset provenance. If a premium generator is unavailable, use recorded app behavior, original diagrams and captions; an unrendered storyboard does not pass the video gate.

## Stage 6 — Release with evidence

**Objective:** deliver a reviewable release and submission package that a newcomer can reproduce.

Completion gates:

- **S6-G1:** a clean supported environment reproduces the documented install/start/demo/diagnose/stop/restart/cleanup path with pinned dependencies. README independently explains purpose, architecture, source layout, limitations and extension examples. Verify behavior-focused tests relevant to the shipped paths.
- **S6-G2:** English Hackster draft contains the concrete sourced problem, architecture/resource tree, protocol and security choices, deployment instructions, actual findings, limitations, repository link and prepared video handoff. Prepare an English presentation and technical Q&A based on actual evidence; record missing authentic public-discussion evidence without manufacturing it. For each article/video/presentation artifact, retain its location, SHA-256, source revision/run IDs and publication state. Unpublished URLs remain pending. After separate publication authorization, the handoff requires article↔repository/video links, the README article backlink and logged-out public-access checks; these are not claimed before publication.
- **S6-G3:** all four teams inspect the release snapshot and all 17 criteria, then perform the maintainer-requested stricter final review after the visual upgrade; unresolved findings have explicit impact and disposition. No unaddressed defect that violates a required gate may be hidden behind a deferral. Source, dashboard, article and video make consistent claims.
- **S6-G5 (added by maintainer during execution):** deliver a single-page HTML pitching/landing-page artifact using actual Three.js visualization. Explain the problem, architecture, oneM2M role, agent workflow and evidence limits. Provide Korean presenter guidance and a complete Korean project explanation, an interactive Three.js workflow comparison and a detailed source-mapped full oneM2M architecture explorer in addition to the facility scene, with camera fitting that keeps rendered components large and legible, usable interactions, responsive/accessibility fallbacks, pinned dependency/license provenance and rendered browser checks. Keep it repository-hostable without publishing to a new external service.
- **S6-G4:** reviewed code/docs/evidence and deliverable locations are committed and pushed through `github-personal`; verify the remote revision. Preserve third-party licenses, exclude secrets/private attachments and record any externally pending publication/submission actions.

## Evidence, state and independent review

The goal is complete only when required stage gates pass with evidence and independent review, every conditional extension has a reviewed adopt/defer decision, all adopted child gates pass, and the release is on the authorized repository. An undecided/investigating extension still needs a disposition; an accepted deferral retains its history. Required gates blocked by credentials or host access keep the goal incomplete. Actual Hackster/video-host/Discord publication and authentic judge interactions are separate handoff items; drafts do not earn their public-evidence rubric credit.

Use `planned`, `implemented`, `verified` and `captured` to describe evidence maturity. Gate status uses `not_started`, `in_progress`, `passed`, `failed`, `blocked_external` or `deferred`; `deferred` applies only to conditional extension gates. A stage may be partially complete while independent work proceeds elsewhere. Each conditional extension has an individual decision and gate record, including advanced SDT/semantic modeling; `required: false` on a parent gate does not waive an adopted child's checks.

For each gate retain the tested code/config revision (or hashes), exact commands and runtime versions, expected/observed outcome, exit status, redacted trace/artifact paths, limitations and the independent review reference. Keep large/raw/private data in ignored local storage; publish compact sanitized evidence and retrieval instructions for permitted artifacts. Do not commit the organizer's PDF/ZIP or credentials. Update [execution-state.json](execution-state.json) after each meaningful milestone and before a context handoff; it is a checkpoint, not a substitute for evidence.

The checkpoint includes active work items (gate, owner role, owned paths, base revision, status, evidence and next action), blockers (affected gates, reason, attempts, alternatives, unlock condition and next independent task), material plan changes (old/new choice, reason, gate impact and review) and per-extension decision history. It also indexes deliverable locations/publication status and the shared live-test accounting. Field contracts are in the state's `record_formats`; empty arrays mean no work/evidence has been recorded, not that a check passed. A reviewer should be able to resume from these records without guessing which worker owns a file or repeating finished work.

Review ownership is unchanged:

| Team | Criteria | Task | Model |
| --- | --- | --- | --- |
| 1 | 1, 2, 3, 11 | `rubric_reviewer` | GPT-6.1 Sol, Max |
| 2 | 4, 5, 6, 7 | `oss_experience_review` | GPT-6.1 Sol, Max |
| 3 | 8, 9, 10, 17 | `architecture_reasonableness` | GPT-6.1 Sol, Max |
| 4 | 12, 13, 14, 15, 16 | `edge_standards_review` | GPT-6.1 Sol, Max |

Use existing reviewers or recreate with `model: gpt-6.1-sol`, `reasoning_effort: max`, `fork_turns: none` and explicit task context. Main plus at most three workers can run concurrently, so batch four-team reviews. Use the same frozen snapshot; log findings in [review/review-ledger.json](review/review-ledger.json). Main chooses accept/alternative/defer, implements or delegates bounded file ownership, and obtains independent verification. Four reviews need not run after every small edit; use affected owners between the full-review milestones above. Review delays do not prevent unrelated implementation, but incomplete review cannot be reported as a passed gate.

## Autonomous execution and fallback policy

The maintainer will be unavailable during the Goal run. Do not ask for routine implementation choices, repeated permission for this repository, or confirmation at stage boundaries. Use the agreed defaults, progress within authorization and provide concise updates while working. This policy does not change the host's sandbox, approval reviewer, account access or budget limits.

Authorized work includes project-local dependencies, code/config/docs/tests, virtual-device execution, bounded tests using an already configured provider, available development tools, independent agents and publication of reviewed project changes to the specified repository. Configure least-privilege ACPs, test-role credentials and TLS inside the project's test environment as required; prefer project-scoped trust rather than changing global trust stores. Do not purchase services, provision paid infrastructure, weaken or change host/account/organization/approval security policies, remove unrelated data, control real devices, distribute private material, send messages or submit to external services under the assumption that unattended operation grants those permissions.

| Situation | Continue with | Keep visible |
| --- | --- | --- |
| Docker/runtime unavailable | A supported project-local runtime or isolated alternative; other service/UI work | Exact missing prerequisite and unexecuted deployment checks |
| No usable hosted model credentials, or shared live-test allowance exhausted | An already available permitted local inference API within the shared allowance if suitable; runner implementation and fixture tests in parallel | Real LLM gate remains incomplete until actual model execution; no automatic counter reset or allowance increase |
| Codex host needs human-only installation/authorization | Plugin/package checks and independent MCP/service tests; all other implementation | Host onboarding remains unverified |
| MEC endpoint/rights unavailable | Local multi-CSE system and reproducible integration interfaces | No MEC deployment/service claim |
| API/transport failure | Diagnose, apply a distinct bounded remedy, then move to independent work if external | Failure reason, next check and affected gate |
| Git push unavailable | Local reviewed commits and a publish-ready bundle; retry after changed connectivity | Remote publication gate remains incomplete |
| Video generator unavailable | Actual screen capture, original diagrams, captions and an available encoder | Video must still be rendered and inspected |
| Approval or organization policy blocks an action | A permitted alternative or unrelated authorized work | Exact restriction; never bypass or weaken controls |

At stage 0, timebox each external feasibility investigation to about 20 minutes before recording its state and moving on. Do not repeat an unchanged failed network/authentication attempt indefinitely; after two equivalent failures, use new evidence or a different permitted path before retrying. These are investigation checkpoints, not limits on useful implementation/debugging. Set explicit per-run LLM steps/tokens/retries/timeouts and a finite shared test-batch allowance before executing API tests; persist consumed/reserved usage across workers and restarts. Use small trials and never create new paid accounts or raise quotas. Exhaustion leaves unfinished live gates blocked while fixture and independent work continue; it does not authorize changing the Goal tool's token budget.

At a blocker: record the affected gate, reason, attempts, permitted alternatives, the condition that would unlock it and the next independent task. Return to the blocker when new evidence/access exists. Preserve checkpoints and continue after context compaction. Do not finish a turn merely to ask whether to continue; do not mark missing execution as successful. If all meaningful authorized paths are exhausted, obey the Goal tool's actual blocked-state rules rather than looping or claiming completion. User-requested pauses and enforced limits still apply.

For the next work item, prefer the action that removes a required dependency or closes a verified high-impact finding with the least new complexity. As the deadline approaches, finish working core behavior, verification and deliverables before opening optional branches. Keep adopted scope and unfinished required gates explicit; an approaching deadline never turns a failed gate into a pass.

## Starting and resuming

Use the [Korean Goal prompt](goal-mode-prompt.ko.md) when ready to activate implementation. This preparatory commit does not activate a Goal. Start at stage 0, or resume the first unfinished gate if execution already exists. Read the latest state and repository before working; do not recreate completed work. Update the plan and state together when dependencies or decisions change.

Goals support an evidence-driven continuation loop; they still have stopping conditions and operate within permissions. See the official [Goals guide](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex) and [Auto-review documentation](https://learn.chatgpt.com/docs/sandboxing/auto-review). The prompt is an execution agreement, not a permission bypass or a guarantee that external services will be available.

# Focused Codex configuration/group case: incomplete

Actual Codex model calls completed `prepare_setup("learning-space")` and
`read_group("learning-b")`. The final concise Korean explanation was **not**
generated within the fixed request limit. This is useful execution evidence,
but it does not close the complete guided-onboarding requirement.

## Distinct scope and fixed limits

The earlier six-request guided rehearsal remains unchanged and partial. This
was a distinct configuration/group acceptance case inside the same shared
100-request / 250,000-token batch. The runtime and virtual profiles were already
installed, running and administrator-activated; these were prerequisites.

The initial 20,000-token allocation was rejected during zero-API preflight:
the projected final request required a 19,553-token conservative reservation,
leaving insufficient room for earlier input usage. Before the first provider
call, the main agent allocated 30,000 of the existing 31,570 shared tokens to
this case. This did not enlarge or reset the shared batch or the earlier case.
The fixed policy was saved before live execution in
`.runtime/codex-config-case-policy.json`; its public copy is
`guided-config-scope.json`.

All other limits stayed fixed: three provider requests across attempts, at most
2,048 output tokens per request, a 45-second provider timeout, a 120-second turn
timeout and no provider retries. Every request had to fit both the case and
the unchanged atomic shared budget before forwarding. No case limit changed
after live execution began.

Only two installed-plugin read tools were exposed: `prepare_setup` and
`read_group`. The model selected their order and arguments. The setup tool
itself returns runtime readiness. Ordinary, scoped one-time MCP approval was
used; no host policy or global Codex configuration was changed.

## Actual attempts

1. In a fresh Codex profile with the installed setup skill, the first model
   request selected `prepare_setup("learning-space")`; it completed against
   the actual service. The next provider request arrived before the first
   stream's usage settlement finished, so the original proxy conservatively
   rejected it. That request was not forwarded. This attempt used one provider
   request and 2,339 tokens.
2. The harness was corrected to serialize the complete HTTP handler, including
   its final usage settlement, with a bounded 45-second lock. A deterministic
   regression test reproduced the premature-reservation failure and confirmed
   that the next reservation waits for actual settlement. It did not release
   or ignore the earlier reservation to make room.
3. The supported `thread/resume` operation could not recover the original
   ephemeral thread because it had no rollout. The unstable history-override
   mechanism was not used. With the main agent's scope decision, the same
   bounded case continued in a new fresh Codex chat: the exact earlier setup
   result was attached as attributed data with its source hash, never as a
   fabricated tool-history message or copied model answer.
4. The model chose to re-check `prepare_setup`, then selected `read_group`.
   Both completed. The native group operation is correlated with independently
   retrieved service run `mcp-0f7558ccb301`. A further request for the final
   explanation was rejected before forwarding: all three case requests had
   been consumed. Its 23,300-token conservative reservation also exceeded the
   remaining 21,970 case-token allowance. No additional inference was run.

The case used **three requests / 8,030 tokens**. The shared batch ended at
**69 requests / 226,460 tokens**, with **23,540 tokens remaining**, no pending
reservations and no usage discrepancy. The case has no requests remaining.

## Claims and limitations

- Proven: actual model-selected setup/profile validation and native group read,
  real Codex skill/MCP execution, ordinary per-call approval, shared service
  correlation, and hard request-budget enforcement.
- Missing: a completed, concise Korean explanation for this focused case.
- The case spans two chats. It is not a single uninterrupted conversation.
- The custom provider proxy and two-tool scope make this an instrumented
  acceptance case, not a claim about the ordinary default Codex provider flow.
- Exact duplicate JSON removal was implemented and checked without dropping
  unique facts; original host results were retained. In these live requests,
  Codex supplied already compact JSON with a `Wall time/Output` text prefix, so
  no context transformation was applied. The earlier size projection used
  captured MCP response wrappers and was only a preflight estimate.
- Software ran against the actual CSE; physical observations and equipment
  remained simulated. A successful group result does not prove actuator ACK.
- All test Codex/proxy processes stopped. Existing application/CSE/broker
  processes were preserved. No profile, role, scenario or actuator was changed.

## Evidence and historical commands

`guided-config-first-settlement-race.json` preserves the first live attempt.
`guided-config-race-regression.json` records the deterministic accounting check.
`guided-config-resume-check.json` records the supported resume failure.
`guided-config-continuation-live.json` contains the exact attributed setup
data, actual model/tool events, original results, independently retrieved group
service run and final budget rejection. `guided-config-checkpoint.json` binds
the evidence and harness hashes. Independent reviewers decide aggregate
acceptance; this report does not advance a stage or close a rubric finding.

The historical continuation command was:

```sh
.venv/bin/python scripts/codex_configuration_rehearsal.py \
  --continue-from evidence/agent/guided-config-first-settlement-race.json \
  --live --output evidence/agent/guided-config-continuation-live.json
```

Omitting `--live` captures a real request without forwarding it. The fixed
case is exhausted; do not reset the policy, shared database or run prefix to
obtain more live calls.

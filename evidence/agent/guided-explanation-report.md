# Captured-record explanation: completed response, factual review open

A genuine Codex 0.166.0 turn completed normally and delivered six Korean
sentences interpreting attributed captured records. The OpenAI response also
completed normally. No operational tool ran in this turn. This establishes
response delivery, not a complete onboarding gate or an unqualified factual
acceptance.

The unedited model output contains one unsupported inference: **“복구 시도는
없으며”** (“there were no recovery attempts”). The source incident has
`recovery_count: 0`, but that field counts consecutive qualifying post-ACK
recovery samples, not attempts. An empty command list in the captured current
run also does not prove that no earlier attempts occurred. This remains a
specific issue for independent reviewers; the model text was not rewritten or
silently corrected. Its wording about the airflow boundary could also be more
precise: the record says airflow was below the configured target, while PM and
CO₂ were above their configured thresholds.

## Scope and provenance

This was a distinct **captured-record interpretation and user handoff** check,
prepared in response to the independent Team 2 advisory. The previous six-call
and three-call cases remain failed/partial, with unchanged caps and originals.
This check does not replay setup, create tool history, claim live observation,
or join the earlier chats into one uninterrupted onboarding conversation.

The fresh Codex profile installed the actual local plugin and selected its
installed setup skill. Its prompt contained exact prior setup/group results
and an explicit JSON-pointer selection from the diagnostic result. All source
files, hashes, capture timestamps, call IDs and the matching MCP revision are
recorded in `guided-explanation-live.json`. The selection retains every
incident and each of the three zone statuses/reasons; native group data already
contains all zone observations. Original records remain independently readable.
No unique conflicting condition was removed to reduce context.

The input identifies these records as untrusted data, declares the
maintainer-installed runtime and preactivated profiles as prerequisites, and
asks the model for its own wording about captured state rather than current
sensor state. No earlier model answer or forged assistant/tool message was
included. The model reports the simulated physical-data boundary, unresolved
recorded classroom condition, unverified real-time/physical outcomes and a
proposed next step. It does not claim to have performed that next step.

## Fixed allowance and observed completion

- One provider request, no retry, at most 2,048 output tokens, 45-second
  provider timeout, and a 22,000-token case reservation limit within the
  unchanged shared 100-request / 250,000-token batch.
- The first zero-API preflight reserved 22,001 tokens and was preserved as
  over the bound. Only redundant instruction wording was shortened; records
  were unchanged. Final dry and live requests both measured 18,725 bytes and
  a conservative 21,797-token reservation.
- Actual use: one request, 4,426 input tokens and 378 output tokens, total
  **4,804**. Provider status `completed`; Codex turn status `completed`;
  six sentences; operational tool calls zero.
- Final shared accounting: **70 requests / 231,264 tokens**, 18,736 tokens
  remaining, no pending reservation and no discrepancy. This case has no
  provider requests remaining.

All test Codex/proxy processes stopped. Global Codex policy, existing runtime
processes, profiles, equipment and both earlier source files were preserved.
The custom provider and disabled operational capabilities are explicit test
instrumentation, not an ordinary-default-provider claim.

## Evidence and historical reproduction

`guided-explanation-live.json` retains the real user-visible answer, host
completion event, provider response identity, source mapping and settled
accounting. `guided-explanation-fact-check.json` provides an author-side source
comparison for the independent reviewers; it is not their approval.
`guided-explanation-checkpoint.json` binds the source/evidence hashes.

```sh
.venv/bin/python scripts/codex_explanation_rehearsal.py \
  --output evidence/agent/guided-explanation-dry.json
.venv/bin/python scripts/codex_explanation_rehearsal.py \
  --live --output evidence/agent/guided-explanation-live.json
```

The live command is historical. The one-request case is exhausted. Do not
reset its policy, database or prefix to repeat inference. R-027 and the full
onboarding gate remain for the main agent and independent reviewers to assess.

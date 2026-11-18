# Cinematic first-pass review — Team 4

Date: 2026-11-18, Asia/Seoul. Scope: criteria 12–16, genuinely useful feasible improvements, and the two-facility/central-outage portion of a proposed five-minute film. This is a bounded first pass over the current local files, not a final candidate approval. No Git commands, inference/provider calls, runtime mutation, external publication or product/article/media edits were performed. Only this review is written.

## Decision

**All five competition criteria remain Expert OPEN.** The latest AGENTS.md makes Expert the target for every criterion. An independently reviewed product-scope deferral does not close a competition criterion. The earlier scoped S4 acceptance remains useful evidence of local continuity; it does not establish serving-CSE handover, MEC, FL or geolocation. No official score, total, N/A policy or award probability is inferred.

The highest-value immediate improvement is to make existing distributed execution legible in the film. A genuine technical candidate requiring no external infrastructure is planned facility-CSE maintenance transition, but that is a new implementation with nontrivial authority/state testing, not a label change to the existing outage experiment. Criteria 13–16 have no presently verified Expert implementation path in the available environment.

## Criterion-by-criterion Expert gates

The following gate descriptions summarize the organizer rubric, whose source SHA-256 is `42b38857fffae7c92739f84440b9db020ec6b79897c0f70db64c465ffd2cdfad`. `docs/hackathon/rubric-baseline.json` is the local map; implementation actions below are reviewer recommendations, not extra official rules.

| Criterion | Every part needed for an Expert claim | Observed evidence and remaining gap | Decision now |
| --- | --- | --- | --- |
| 12 CSE Handover & Service Continuity | Automatic handover triggered by location, load, latency or availability; preserve/rebuild state, subscriptions and security context; measure interruption or data loss. | `evidence/runtime/product-multisite-continuity.json` records actual fixed-MN local continuity, not a serving-CSE change. No automatic source-to-target CSE transition, restored target context or transfer measurement exists. | **OPEN.** A maintenance/availability transition is the only plausible local technical spike; require the complete acceptance below before upgrading a claim. |
| 13 oneM2M–MEC Application / VM Deployment | A custom deployment scenario reflects project-specific geography/topology and oneM2M–MEC services, and demonstrates orchestration across eligible hosts. | Local AE/CSE deployments, native registrations and instructions are real. `evidence/stage0/mec-feasibility.json` establishes neither authenticated MEC hosting nor image/orchestration rights. | **OPEN.** Keep the real local-deployment evidence, but do not call it managed MEC or Expert orchestration. No new external infrastructure is recommended. Reopen when an already-permitted host/eligible hosts and deployment/log access exist. |
| 14 Federated Learning (TR-0084) | Custom oneM2M models coordinate participants, datasets/tasks, status and results; dynamic client selection; resilient multi-round learning; ESTIMED VM use. | No suitable multi-site learning dataset/task, actual training/aggregation, participant selection or ESTIMED VM execution. Hosted model tool use is inference, not FL. | **OPEN.** No useful immediate FL feature is justified. A synthetic FedAvg example without the product learning need and ESTIMED VM would not close this gate. |
| 15 Geolocation Services | Combine network/MEC/oneM2M location services to support a relevant mobility/handover/geofence/placement/policy use case and demonstrate event-driven behavior. | Fixed facility/zone identity and 3D coordinates are configuration/presentation. No actual location-service interworking or resulting operational event is captured. | **OPEN.** Do not invent a mobile cart/responders solely for coverage. Reopen for a genuine moving asset whose actual service event changes a necessary operation. |
| 16 MEC Services | Discover, configure and consume multiple MEC services through oneM2M; demonstrate bidirectional MEC–oneM2M interaction. | oneM2M discovery, MCP and the local intent workflow are real, but no supported non-location MEC instance is consumed through an IPE. MEC033 availability remains unestablished. | **OPEN.** Product-relevant platform onboarding/discovery remains a candidate only. Actual service access through CSE/IPE, returned application behavior and reverse interaction would all need capture. |

For #13 and #16 the precise absence is a verified environment and execution, not proof that the public platform is globally unavailable. A public homepage response or a session-specific reset cannot settle service availability, permissions or competition applicability.

## Improvements that are reasonable now

### P0: evidence-derived two-site outage sequence

- **Need:** a facility manager must understand what stays available when central visibility disappears, and what happens to delayed requests.
- **Smallest improvement:** build a readable recorded-trace sequence from the existing topology JSON, paired with the source-mapped architecture. Show `central unavailable`, the local command/ACK/later recovery, then expired/wrong-profile rejection and the valid replay result. Use the actual recorded identifiers and timestamps; label edited or time-compressed replay.
- **Benefit over a generic cloud animation:** it explains a tested operational failure and local authority with inspectable evidence, without inventing a live network or physical experiment.
- **Acceptance:** every displayed event/value resolves to a JSON field in the named run; no current-source recapture is claimed; protocol profiles remain separate. This improves article/video/promotion evidence, not Expert implementation of #12–16.

### P1: bounded feasibility of a real planned-maintenance CSE transition

- **Need:** planned replacement/maintenance of a facility gateway can require the same facility diagnosis and pending maintenance incident to continue on a target CSE. This is plausible but must be explicitly adopted as an operating requirement before implementation.
- **Existing assets:** real CSE processes, reusable facility identity/profile, durable incident/run state and per-command expiry/idempotency. A separate target resource namespace on an existing test CSE avoids external infrastructure; protect the other facility's state and do not stop unrelated work.
- **Simpler alternative:** the present system already handles central-link loss. If local-CSE maintenance continuity is not actually needed, retain the simpler design and keep #12 open.
- **First bounded spike:** verify that a facility can be provisioned at a target CSE with a stable application-level asset identity and a documented new CSE-local AE mapping. Explicitly test re-creating subscriptions and least-privilege ACPs. Stop the spike if the chosen CSE cannot support the required mapping/restoration without unsafe state copying.
- **Full Expert acceptance if adopted:** a repeatable availability/maintenance condition automatically changes the serving CSE; transfers policy version, active incident/run, last observation sequence, outstanding command/ACK and unexpired override as applicable; restores subscriptions and ACPs; prevents simultaneous/old-controller command execution; rejects delayed/duplicate commands; measures interruption and missing observations against an uninterrupted baseline. Actual CSE endpoint/registration changes must be visible.
- **Limit:** a manual restart against another endpoint is useful feasibility or controlled handover evidence, not the full automated Expert descriptor. Moving an application context is not process/VM migration. Announcements are not a replication mechanism. An isolated successful transition does not prove abrupt-failure HA.

An always-running central intent receiver could also have a genuine multi-site operations benefit, because the current receiver is explicitly invoked by the demo driver. If the product adopts that need, prefer a native subscription with reconnect replay reconciliation, using the existing scope/profile/expiry/idempotency guards. It would strengthen the existing application workflow, not satisfy handover or MEC. It is lower priority than truthful film capture and is not required merely to fill a rubric row.

## What the existing distributed evidence actually proves

Primary run: `topology-549e41103a` in `evidence/runtime/product-multisite-continuity.json`.

| Evidence selector | Film-safe fact | Claim boundary |
| --- | --- | --- |
| `checks.central_product_discovery_before_outage` | Central requests discover/read food-a and learning-b observations from their MN-CSEs. | Actual processes run on one host; not geographical deployment. |
| `evidence/runtime/cse-multisite-smoke.json` → `native_remote_CSE_registrations`, per-site discovery/read/denial, selective announcements | Native registration/routing/ACP/announcement behavior. | Announcement is selective resource sharing, not general state replication. |
| `checks.central_unavailable` | IN-CSE was stopped; the request returned ConnectError / response code 0. | One bounded local central-outage experiment, not a real Internet outage. |
| `checks.local_recovery_while_central_down` | `demo-4ee9341e43`, command `cmd-07e9bed57aac`: local command, virtual-device ACK and later CSE observations establish the scenario recovery. | Deterministic fixture, not an LLM making those outage decisions. All physical readings/responses are simulated. |
| `checks.reconnected_product_state.outage_seconds` | Recorded central interruption: **14.635 seconds**. | A single recorded run, not an SLA or handover latency. Do not round it into a guaranteed recovery claim. |
| `container_state_tag_delta_between_central_snapshots` | Food zone tags advance by 9 and learning zone tags by 8 during the snapshot gap. | Not a packet-loss count, zero-loss result or complete history replay proof. |
| `checks.delayed_and_wrong_profile_intents` | `central_intent_expired` and `central_profile_mismatch`; command IDs and local incidents stay unchanged. | Rejection is performed by the facility service after reading CSE data; do not label it a native CSE expiry refusal. |
| `checks.central_cannot_bypass_local_authority` | Direct central command write receives oneM2M 4103. | Distinct AE/ACP check within the disclosed trusted-loopback actor boundary. |
| `checks.fresh_central_intent_local_policy_ack_recovery` | Valid learning-b intent yields one command, ACK and verified result; replay returns that command. | Explicit test-driver replay, not an always-running federation dispatcher. |

The capture's `core.py` and `app.py` hashes are older than current files. `docs/review/final-team4.json` and `final-closeout-team4.json` already assess the bounded ownership/setpoint/metadata delta; the other 12 topology source hashes remain equal in this first pass. Keep the historical run and source scope attached. A later candidate change requires affected-source comparison again.

## Assets available for a five-minute film

| Asset | Useful shot | Limits / missing material |
| --- | --- | --- |
| `evidence/pitch/architecture-full-distributed.jpg`; `architecture-release-desktop.jpg`; `pitch/architecture.js` | Establish two facility APIs, two MN-CSEs and central IN-CSE. Use a controlled push-in from the source-mapped explorer. | Static explanatory view. Forty-six components include native resources and logical modules; they are not 46 processes. Agent links in this topology are shared contracts, not a separately executed distributed model session. |
| `evidence/pitch/architecture-full-single-command.jpg` | Contrast the simple installation with the distributed lab. | Secure MQTT/TLS/HTTPS is the alternative single installation. Distributed Mcc remains HTTP. |
| `deliverables/video/frames/scene-07.png` and `evidence/video/decoded-82s.jpg` | A clean two-profile/vendor visual, visually inspected in this pass. | Diagram of two implemented profiles/adapters; it is not runtime proof that two physical facilities are connected. |
| `evidence/dashboard/visual-upgrade-desktop-unresolved.jpg`; `desktop-no-recovery.jpg`; `web/facility-3d.js` | Actual application state, fan/flow distinction and acknowledged-but-unresolved outcome. | Single-installation capture with virtual telemetry. Do not splice it as the live dashboard of the historical two-site run without a replay label. |
| `evidence/runtime/product-multisite-continuity.json`; `scripts/cse_product_topology.py` | Authoritative outage timeline and short legible terminal/trace inserts. | No existing continuous outage screen recording was found in the inspected asset inventory. A trace-based reconstruction must be labelled. |
| `deliverables/video/openSoom-demo-en.mp4`; `evidence/video/asset-provenance.json`; narration/captions | Existing 108.021-second 1080p English film, with actual UI still sequence and model traces. | It contains the two-profile diagram but no sustained actual two-site central-outage sequence. Extending its duration alone does not close Expert gaps. Preserve historical run/source attributions. |

Suggested **60–70 seconds within the five-minute film**, rather than spending the entire film on topology:

1. **0–12s:** establish two facility cards and the optional central IN-CSE. Caption: “Two local facility services · real oneM2M CSEs · virtual equipment.”
2. **12–24s:** actual central discovery/announcement identifiers. Highlight one native response, not a wall of JSON.
3. **24–42s:** central goes unavailable while the food facility's local command → ACK → two later observations complete. Caption: “Replay of recorded test topology-549e41103a”; show the recorded interval or disclose time compression.
4. **42–56s:** central reconnects; expired and wrong-profile intents are refused. Then a single valid learning-facility intent is accepted.
5. **56–68s:** repeat the valid request ID, show the same command ID. End: “Local control stays local. Central visibility returns. This test is continuity, not CSE handover or MEC.”

Do not interleave events from different runs as one uninterrupted operational sequence. If main elects a fresh deterministic capture, coordinate the isolated test window before invoking the topology script because it stops the central CSE; retain pre/post source hashes, actual recordings and any failed attempts. No new model call is needed for this distributed fixture.

## Publication and cinematic acceptance boundaries

- The current article is explicitly a draft; public Hackster/video URLs and team-channel submission are pending handoff. A prepared MP4 or a GitHub source link is not an already published Hackster/video submission.
- The article correctly separates secure single-installation and distributed HTTP profiles, cohosted logical roles, actual software and virtual physical behavior. Preserve those captions in any new 3D treatment.
- A cinematic outage animation is explanatory evidence presentation. It cannot close a missing backend/MEC/FL/location gate. Avoid “seamless handover”, “zero loss”, “MEC powered”, “real-time digital twin”, “certified safe ventilation” or physical/clinical improvement language without corresponding evidence.
- PM/CO₂ and a running fan do not prove capture adequacy. Use “profile-specific simulated target”, and show ACK separately from observed recovery.
- Use actual recorded values and units. Add a short source/run reference on screen and a full evidence/provenance index in credits/article; redact credentials and preserve third-party attribution.

## Candidate-review acceptance

For the next pass, supply the exact candidate or file hashes, final five-minute video, captions/narration, storyboard/shot-to-evidence map and final article. Team 4 will check every distributed shot against source/run IDs, protocol profile and claim boundary, and review any newly adopted #12–16 execution separately. This first pass does not close any of those five Expert gates.


## Local evidence hash record

Working-set hashes observed at completion of this first pass; no immutable candidate was supplied for this turn. A final candidate review must recheck affected files.

| Path | SHA-256 |
| --- | --- |
| `AGENTS.md` | `c644b2587575e9947cb1820be6a6aaf0a94b6cffb7d91a1a6429103ed0c1af47` |
| `docs/hackathon/current-assessment.md` | `3f6b50b9df3046047d91f4fc1ba439687db9eaa7a080b87c35fb5399da85e4bb` |
| `docs/hackathon/rubric-baseline.json` | `2eddd5ef6bb2bf7bb9354b92a432512546be3b522e3f84724d016b4dd2055a94` |
| `docs/extension-decisions.md` | `995d57f7bbc24c752f625507d61ed55db0800fad69151ab78dac48d0b295e973` |
| `docs/submission/hackster-article.md` | `8aa3a6176d1a2959003780d060260b7259353cd28c32b85528ce1b029357c51d` |
| `evidence/runtime/product-multisite-continuity.json` | `177da67f736ae8887debc8b02474c03f4a73d1330221ebeb4d8ca4aada85fed2` |
| `evidence/runtime/cse-multisite-smoke.json` | `48167af50668bd2d0a26e41f03aa2df71122024b0d3e45c97da1f784c66e67ed` |
| `evidence/stage0/mec-feasibility.json` | `2108e8b647b7ea2f1605abb8bf2937fe5108bac8f7d7caab84ddb57b5189b5d5` |
| `src/opensoom/core.py` | `00f4339ce5481d4daf13f8d44ab857f86173469f8da68eddf0db96d5ca6c32c5` |
| `src/opensoom/app.py` | `90b2b13f78732ed32ac22fa0e21c9669d4731180463e80bbe551f881e622a144` |
| `evidence/pitch/architecture-source-map.json` | `dc328c6e85abdeed24908b63798d11d2d2177514242143b4fcb7608b90fb9c83` |
| `deliverables/video/openSoom-demo-en.mp4` | `d4cc9e2ce19fcef31f97212edf54f0ae5caa5c32e2f17e5ae8ae7ce32721c0ee` |

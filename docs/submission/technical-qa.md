# Technical interview and presenter notes

Use the single-page `pitch/index.html` for the presentation. Its Korean speaker guide explains the English story. The video supplies a short captured demonstration; use the live local dashboard for a longer inspection.

| Judge question | Evidence-based answer |
| --- | --- |
| What precise problem do you solve? | The manager must distinguish equipment status from the intended observed condition and track authorized action through ACK to later evidence. The example is a running fan with insufficient configured airflow in a food-production zone. |
| Why oneM2M instead of a custom API? | Multiple application roles and vendors share resources. Native discovery, subscriptions, fan-out, ACP and Mcc reduce duplicated common-service code. A single-vendor isolated use case may need less machinery. |
| Is this only a kitchen product? | No. Food-production and learning-space profiles plus two adapters use the same core and tools. Configured targets remain facility-specific. |
| Are the readings or health benefits real? | Physical readings and actuators are simulated. CSE, native protocols, MCP and hosted-model execution are real. No health outcome or certified ventilation performance is claimed. |
| Does an ACK mean success? | It only establishes that the virtual device acknowledged the current command. Two unique fresh healthy observations after ACK are required. A separate non-recovery run stays unresolved. |
| What does the LLM decide? | It chooses structured operational tools and a bounded action using observed results. Server roles, facility/profile scope, freshness, idempotency and result checks enforce the boundary. It cannot grant itself administrator access. |
| What persists across chats? | Service-owned runs, commands, incidents and event records. MCP host sessions receive their own run context. CSE resources and SQLite state persist separately. |
| Is your MQTT integration native? | Yes. Captures show oneM2M request/response primitives on the CSE MQTT binding and the same resource read over HTTPS. It is not an HTTP bridge. |
| How is SDT used? | Actual discovered cod:aiQSr flexContainers expose integer PM2.5 in µg/m³. Canonical CINs preserve precision and timestamps. CO₂ ppm and volume airflow are not forced into incompatible standard fields. |
| What happens when one group member is denied? | This ACME version returns a top-level4103 in that case. We retain that native error and label separate member diagnostic reads. We do not fabricate a mixed native aggregate or call it actuator success. |
| Is the system secure? | Project-local HTTPS/MQTT TLS validates servers, and scoped AE ACP tests show allowed and denied operations. Local clients are trusted: origins are not cryptographic device identities and MQTT is anonymous loopback. No production security claim. |
| Does a central outage stop local operation? | The actual test stops the IN-CSE. Each facility's local CSE/API continues the defined observation/action/ACK/recovery path. Expired and mutated central replays are rejected. |
| Is that CSE handover or MEC? | No. The serving facility CSE does not change. MEC hosting/services and handover require separate execution. Their investigated deferral is recorded; they are not treated as official N/A. |
| How would a manager adopt it? | A maintainer installs the supported local runtime. The Codex plugin guides readiness, profile inspection, discovery, diagnosis and verification. New facility records use configuration. A real device protocol and a nontechnical first-use study remain further work. |
| What did testing change? | We fixed cross-run reuse of historical command success, preserved requested virtual actuator percentages, restricted run writes to the owning role, and preserved secure settings and pending incidents across stop/start. Failed captures remain traceable. |
| What evidence should we inspect first? | The agent evidence index, actual CSE runtime traces, application acceptance, clean lifecycle rehearsal, distributed continuity capture and four-team review ledger. |

## Suggested five-minute sequence

1. 40 seconds: concrete source and the running-fan/airflow gap.
2. 50 seconds: explain the common facility model and two vendor formats.
3. 60 seconds: use the Three.js architecture view to locate adapter, CSE, service and MCP.
4. 70 seconds: walk through action, distinct ACK and two later observations; contrast the observed unresolved case without claiming health impact.
5. 40 seconds: explain central outage, intent expiry and local authority.
6. 40 seconds: show the installation path, evidence and honest extension limits.

Authentic public technical exchanges and the actual judge interview have not occurred within this automated work. This preparation is not evidence for participation points.

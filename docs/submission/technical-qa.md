# Technical interview and presenter notes

Prepare an English slide deck for the evaluation and upload it to the organizer's Drive folder by Sunday, 22 November 2026. The local Three.js pitch and its Korean speaker guide supply visuals and rehearsal material. Play the English demo during the talk. The organizer allocated 20 minutes per team and requested a 10–15 minute presentation including the video, followed by questions.

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

## Twelve-minute evaluation presentation

| Elapsed time | What to show | What the presenter should explain |
| --- | --- | --- |
| 0:00–0:45 | Food-production zone, fan running, simulated airflow 360 m³/h against its configured 900 m³/h target | Why checking a zone after installation matters. Attribute the school-kitchen performance assessment to its published source. |
| 0:45–2:05 | Two facility profiles, two vendor adapters, one operations service | Which settings change by facility and which parts of the software another operator can reuse. |
| 2:05–3:10 | Resource tree, three group members and one observation written over MQTT/TLS and read over HTTPS | Show the shared resource ID. Explain why the device publishes while the management application queries. |
| 3:10–8:10 | Play the full [five-minute English demonstration](../../deliverables/video/openSoom-demo-5min.mp4) with shared audio | Introduce the food and learning facilities. Let viewers follow the dashboard recordings and the separate operations and maintenance workers. |
| 8:10–9:25 | One fault observation, two applications, one inspection that stays open | Show the common source CIN and separate read request IDs. Explain why an operator can issue a damper command while the maintenance role cannot. |
| 9:25–10:30 | The hosted model's recorded tool calls and a fresh observation | Identify the decisions made by the agent and the rules enforced by the service. Contrast the recorded recovered and unresolved outcomes. |
| 10:30–11:25 | The second adapter, standard PM2.5 read and account-free installation | Show what an adopter can reuse before connecting physical devices. |
| 11:25–12:00 | Next installation and the public repository | Explain the first read-only pilot measurement and why the next integration would keep oneM2M. |

This plan leaves about eight minutes for questions and transitions. Join the meeting before the assigned slot. The organizer confirms the slot with `PICK` in the evaluation sheet and a Discord update.

Authentic public technical exchanges and the actual judge interview have not occurred within this automated work. This preparation is not evidence for participation points.

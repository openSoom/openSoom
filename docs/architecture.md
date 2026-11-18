# Architecture and operational reasoning

openSoom separates facility configuration, vendor integration, standard shared services and operator decisions. Complexity follows an operating need: the same data must serve diagnosis, authorized operation and maintenance, and local work must continue during a central outage.

## Applications and trust

| Component | Responsibility | Why it exists |
| --- | --- | --- |
| Adapter AE | Normalize virtual vendor payloads, write observations, read commands, send ACK | Vendor replacement must not change diagnosis or agent tools |
| Diagnostic AE | Read CSE observations and apply profile targets | A fan-running report alone cannot establish sufficient airflow |
| Operator AE | Inspect zones and issue allowed bounded commands | Facility operation has different authority from observation |
| Edge maintenance AE | Read the site outcome, request an independently measured shaft position and revise a work order | An unresolved airflow shortfall can have several causes |
| MEC service bridge | Discover the configured provider, commission the connection through MEC 033 and return a MEC 046 reading with its source and time | A provider can manage its own sensor independently of the damper controller |
| Technician web app | Append a field disposition for the exact order revision using a dedicated site identity and keep field notes in a separate private stream | The operator needs the inspection status. The technician owns the field record and has no equipment command permission |
| Observer AE | Read only configured facilities | Validate restricted sharing independently of administrator access |
| CSE | Store resources, discover, notify, fan out and enforce ACP | Shared behavior must be provided by the standard layer |
| Service | Persist runs/incidents and enforce tool policies | State must survive a chat or service restart |
| MCP server | Structured facility setup, discovery, diagnosis and virtual-trial tools. Each client can limit which tools it exposes | Agent convenience must use the same operational boundary |
| Central operator | Read selectively shared resources and issue expiring intents | Multiple sites need oversight without making local control depend on the WAN |

These are distinct application identities and responsibilities. The local prototype cohosts them in a small number of processes. It does not claim independent production services merely because several AEs are registered. The distributed test runs two actual facility APIs against separate MN-CSE processes.

## A second application at the edge

The operations AE alone can command a device. The maintenance AE opens an inspection and requests independent shaft position for that asset. The separate service bridge is allowed to contact a configured provider and return its response to the facility MN-CSE. Maintenance reads that response through its own scoped identity. The bridge and maintenance cannot write device commands. An administrator commissions a missing provider via MEC 033. MEC 046 then supplies a fresh reading. A facility that already receives the same independent observation locally can use that route. [Services and work-order revisions](../evidence/runtime/mec-provider-commissioning.json)

In Option C, the Sandbox controller and its Helm engine install the ACME MN and the maintenance workload on the same logical edge. The scenario author selected north and then south in a two-edge topology on one physical VM. In each deployment the MN registered to its IN-CSE over Mcc and a new case reached revision four. The persisted earlier case could be read after the move. [Deployment and repeatable commands](../deploy/mec-sandbox/README.md) · [North and south receipts](../evidence/runtime/option-c/index.json)

## What the two people see

The operator console follows an authorized command from ACK to two new observations. When airflow stays below the commissioned target, the operator opens that exact work order in the independently served technician workbench. The technician compares the requested and measured positions, then records an inspection status against the immutable work-order revision. The operator sees the status. A private field note stays accessible only to the technician role. Saving the entry leaves the device command count and incident outcome unchanged. The worker selects a first check. An onsite inspection determines the physical cause. [Live replay and role boundaries](../apps/technician/README.md) · [Browser evidence](../evidence/application/technician-browser.json) · [18-case comparison](inspection-benchmark.md)

## Resource tree

```text
cse-secure
├── os-adapter / os-diagnostic / os-operator / os-maintenance / os-observer (AE)
└── opensoom (AE)
    ├── acp-food-a-{structure,observations,commands,acks} (ACP)
    ├── acp-learning-b-{structure,observations,commands,acks} (ACP)
    ├── facilities (CNT)
    │   ├── food-a (CNT)
    │   │   ├── cook (CNT)
    │   │   │   ├── observations (CNT) / CIN / diagnosis (SUB)
    │   │   │   ├── commands (CNT) / CIN
    │   │   │   └── acks (CNT) / CIN
    │   │   ├── wash (same containers)
    │   │   └── pack (same containers)
    │   └── learning-b / classroom, meeting, lounge
    ├── food-a-zone-observations (GRP, observation CNT members)
    ├── learning-b-zone-observations (GRP)
    └── {facility}-{zone}-air (FCNT, cod:aiQSr)
```

Each protected container has its own explicit ACP reference. Content instances inherit their parent container's policy. The bundled ACME version does not make an absent CNT `acpi` inherit its AE's policy. Administrators provision resources; ordinary operations use the assigned AE origin.

## One incident from observation to outcome

1. The adapter converts its wire values and creates an observation CIN using native oneM2M MQTT/TLS. Original floating-point precision stays in the observation. It updates the standard PM2.5 flexContainer separately.
2. A subscription callback prompts a fresh CSE read. The callback body alone is never trusted as the measurement. CIN resource identity deduplicates notification/read paths.
3. Diagnosis checks the configured measurements, timestamps and targets. Missing or stale evidence cannot authorize control. A running fan with deficient airflow opens an incident.
4. A structured tool request passes role, facility, zone, profile, allowed-action, bounds and freshness checks. The service creates a command CIN with an idempotency key, run association and expiry.
5. The virtual adapter reads the actual command from the CSE and creates a distinct ACK. A command write or group success cannot stand in for this ACK.
6. Two unique healthy observations after ACK establish recovery. Missing ACK times out. Two later deficient observations establish non-recovery. Maintenance records do not prove recovery.

The service persists run ID, commands, incidents and events in SQLite. Public traces correlate those IDs with native CSE request IDs. Historical commands cannot satisfy a new run, and identical repeated reads cannot count as separate recovery samples.

## Distributed demonstration

The optional local topology runs central IN-CSE 8180 and facility MN-CSEs 8181/8182. Native Mcc registration, remote resource reads and selective announcements support central visibility. Facility APIs use separate SQLite stores. A central outage does not stop local observation, diagnosis or authorized action.

The demonstrated reconciliation rule is conservative: a central intent names a configured queue, facility, profile/version, issue time, expiry and request ID. The facility rejects expired, future, mismatched or mutated replays before dispatch. A valid intent goes through the same local policy and idempotency checks. Central ACP cannot directly write local command containers. The replay test is explicit; no always-running federation consumer is claimed.

## Simpler alternatives and limits

A single-vendor system can connect directly to its API. The prototype adds oneM2M when observations and controls must be shared across vendors, applications and facility CSEs. Profiles keep site targets out of integration code. MCP provides a guided interface without replacing the standard.

The two-CSE handover lab restores an incident, its pending command, subscriptions and scoped access after the serving CSE is taken down. The local operating demonstration covers site-specific airflow targets. Physical fan balancing, capture efficiency and learned threshold selection are outside the measured cases. [Handover measurements](../evidence/runtime/handover/acceptance.json) Each zone follows its configured target and bounded damper scenario. Adding those mechanisms requires a measured need and separate acceptance evidence.

HTTPS/MQTT TLS encrypt and authenticate the project servers. Loopback origin headers and anonymous lab MQTT clients are trusted local actors, not authenticated physical devices. The API and callbacks use local HTTP, and the distributed profile uses HTTP between CSEs. See [deployment boundaries](../deploy/README.md).

# Architecture and operational reasoning

openSoom separates facility configuration, vendor integration, standard shared services and operator decisions. Complexity follows an operating need: the same data must serve diagnosis, authorized operation and maintenance, and local work must continue during a central outage.

## Applications and trust

| Component | Responsibility | Why it exists |
| --- | --- | --- |
| Adapter AE | Normalize virtual vendor payloads, write observations, read commands, send ACK | Vendor replacement must not change diagnosis or agent tools |
| Diagnostic AE | Read CSE observations and apply profile targets | A fan-running report alone cannot establish sufficient airflow |
| Operator AE | Inspect zones and issue allowed bounded commands | Facility operation has different authority from observation |
| Maintenance AE | Record maintenance requests and inspect evidence | A failed recovery needs a distinct follow-up path |
| Observer AE | Read only configured facilities | Validate restricted sharing independently of administrator access |
| CSE | Store resources, discover, notify, fan out and enforce ACP | Shared behavior must be provided by the standard layer |
| Service | Persist runs/incidents and enforce tool policies | State must survive a chat or service restart |
| MCP server | Eight structured tools shared by Codex and API runner | Agent convenience must use the same operational boundary |
| Central operator | Read selectively shared resources and issue expiring intents | Multiple sites need oversight without making local control depend on the WAN |

These are distinct application identities and responsibilities. The local prototype cohosts them in a small number of processes. It does not claim independent production services merely because several AEs are registered. The distributed test runs two actual facility APIs against separate MN-CSE processes.

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

The demo does not optimize a shared fan's physical flow allocation, infer capture efficiency, learn thresholds, migrate processes or implement serving-CSE handover. Each zone follows its configured target and bounded damper scenario. Adding those mechanisms requires a measured need and separate acceptance evidence.

HTTPS/MQTT TLS encrypt and authenticate the project servers. Loopback origin headers and anonymous lab MQTT clients are trusted local actors, not authenticated physical devices. The API and callbacks use local HTTP, and the distributed profile uses HTTP between CSEs. See [deployment boundaries](../deploy/README.md).

# Local oneM2M runtimes

openSoom uses **ACME CSE 2026.5.3**, a real oneM2M service layer. Devices and their readings are simulated; resource creation, subscriptions, discovery, access control, groups, announcements, and protocol bindings execute in the CSE. The runtime is separate from the application environment and does not require Docker.

## Prerequisites and startup

Install Python **3.12**, `uv`, and OpenSSL, then run commands from the repository root. This path was exercised on macOS with Python 3.12.12. Other operating systems still need their own installation evidence.

```sh
# Small, single-facility development installation: HTTP 8080.
python3 scripts/cse_bootstrap.py single

# Independent HTTPS 8443 + native MQTT/TLS 8883 profile.
python3 scripts/cse_bootstrap.py secure

# Independent IN-CSE + two MN-CSEs on 8180, 8181, 8182.
python3 scripts/cse_bootstrap.py multisite
```

The first run installs pinned dependencies from `cse-requirements.txt` and, for the secure profile, `mqtt-requirements.txt`. Network access to the package index is needed for missing packages. Use `--skip-install` after installation. Repeating a start command preserves an already-running profile and its database. The application server uses port 8090; these commands do not start it.

| Profile | CSE base URL | Base resource | CSE-ID |
| --- | --- | --- | --- |
| single | `http://127.0.0.1:8080` | `cse-in` | `/opensoom-in` |
| secure | `https://127.0.0.1:8443` | `cse-secure` | `/opensoom-secure` |
| central | `http://127.0.0.1:8180` | `cse-central` | `/opensoom-central` |
| food | `http://127.0.0.1:8181` | `cse-food` | `/opensoom-food` |
| learning | `http://127.0.0.1:8182` | `cse-learning` | `/opensoom-learning` |

Readiness requires a real CSE retrieval returning oneM2M response code 2000. The secure profile also requires a certificate-verified broker handshake. It can take up to 45 seconds to start a CSE. A failed readiness check reports its project-local log path instead of printing configuration secrets.

## Inspect, stop and reset

```sh
python3 scripts/cse_runtime.py status --name secure
python3 scripts/cse_broker.py status
python3 scripts/cse_runtime.py stop --name secure
python3 scripts/cse_broker.py stop
```

Use names `single`, `central`, `food`, or `learning` to manage those CSEs. Stop the two MN-CSEs before their central IN-CSE. The stop command checks the recorded process command before signaling it. If a stale process record names an unrelated process, that process is left alone.

Reset is explicit and affects the named CSE's database. Stop it first, then start with `--reset`; for example:

```sh
python3 scripts/cse_runtime.py stop --name food
python3 scripts/cse_runtime.py start --name food --port 8181 --registrar-port 8180 --reset
```

Runtime environments are under ignored `tmp/runtime/cse-venv/` and `tmp/runtime/mqtt-venv/`. Generated CSE configurations, logs, databases, process records, and certificates are under ignored `.runtime/`. The two environments are deliberately separate because the CSE and broker need different WebSocket dependency versions. Do not commit these directories. Removing a named `.runtime/cse-<name>/` directory after stopping it removes that CSE's data. Removing `.runtime/pki/` changes the lab CA; stop the secure CSE and broker first, then restart them and use the new CA in clients.

## Actual protocol checks

Each smoke script creates uniquely named resources, checks outcomes, and cleans up those resources. It does not reset another application's CSE state. Use the CSE environment to obtain the pinned HTTP and MQTT clients:

```sh
tmp/runtime/cse-venv/bin/python scripts/cse_smoke.py
tmp/runtime/cse-venv/bin/python scripts/cse_smoke.py --url https://127.0.0.1:8443 --base cse-secure --ca-file .runtime/pki/ca.crt --evidence evidence/runtime/cse-https-smoke.json
tmp/runtime/cse-venv/bin/python scripts/cse_mqtt_smoke.py
tmp/runtime/cse-venv/bin/python scripts/cse_multisite_smoke.py
```

Sanitized results go under `evidence/runtime/`. They contain request identifiers, response codes, timestamps, resource identifiers, and simulated data. These are runtime checks, not independent rubric reviews or certification results.

The native MQTT check creates a content instance through `/oneM2M/req/.../opensoom-secure/json`, receives the matching native response, and reads the identical resource through HTTPS. It also checks an unprivileged operation is denied, verifies TLS 1.3 on both listeners, and verifies the project certificate is rejected without the explicit project CA.

The subscription smoke's callback receiver is a temporary loopback HTTP listener. The secure smoke creates the subscription through HTTPS; it does not claim TLS on that callback leg.

The multi-site check registers two real MN-CSEs with an IN-CSE, forwards discovery and retrieval through the central CSE, enforces read-only central access, denies an outsider, and reads back unique selective container announcements. A shared container needs its **own explicit `acpi`**: in this ACME version, a container that supports `acpi` does not inherit its AE's ACP when that attribute is absent. Content instances inherit the parent container's access control. Remote paths use the HTTP SP-relative form `~/opensoom-food/cse-food/...`.

## Distributed product continuity

After installing the application environment, run the actual product scenario:

```sh
.venv/bin/python scripts/cse_product_topology.py
```

This starts isolated facility APIs on **8091/8092**, with fresh stores in `.runtime/product-topology/<run-id>/`. Food production uses MN-CSE 8181 and the learning facility uses MN-CSE 8182. It preserves the ordinary single CSE 8080 and application 8090. The script starts the existing multi-site CSE profile if needed; it expects the pinned CSE environment already installed.

The central operator first discovers and retrieves actual openSoom zone observations. Their container announcements use native CSE sharing. The script stores a short-lived central intent, stops only the central IN-CSE on 8180, and runs the food facility's local `exhaust_fault` scenario. Local CSE commands, virtual-device ACK, and later observations establish recovery while the central CSE is unavailable. It then restores the central CSE, reads current observations and their age against each facility profile, and records the gap between central snapshots. State-tag differences show changes during the gap; they are not a packet-loss measurement or a claim of complete history replay.

`FederationReceiver` in `src/opensoom/federation.py` reads an already-retrieved CSE intent and checks its configured queue, facility, active profile/version, timestamps, bounded lifetime and request ID. It uses a fixed local operator scope, then calls the same `Core.request_action` policy path as the service. The payload cannot select a role, endpoint or credentials. Durable receipts plus a process lock and Core idempotency keep replay from dispatching another action. A rejected expired intent remains rejected after another retrieval; changed content with a reused request ID conflicts.

The recorded run checks expired and wrong-profile intents leave command and incident state unchanged, and that an attempted direct central command write is denied by CSE ACP. Expiry rejection happens in the facility service after a successful CSE read; it is not described as a native CSE expiry check. A fresh central intent for the second facility also passes local policy, receives an ACK, and reaches verified recovery; replay returns the same command.

Results are saved to `evidence/runtime/product-multisite-continuity.json`. By default, the script stops its two facility APIs and leaves the restored CSE cluster available. `--keep-running` keeps the facility APIs for inspection. The central intent and receipt evidence remains in the project runtime. This is an explicit replay demonstration, not an always-running federation consumer, serving-CSE handover, MEC deployment, or full recovery from an abrupt facility-process failure.

## Transport and actor trust boundary

All listeners bind to **127.0.0.1**. The development profiles trust local processes. The HTTP origin `CAdmin` is a privileged test administrator; an origin string is not a password or a cryptographic identity. Normal application operations should select scoped AE origins on the server, never accept model-supplied identities, and verify denied operations with an unprivileged origin.

The secure profile provides **server-authenticated HTTPS and MQTT/TLS** using a private project CA at `.runtime/pki/ca.crt`. Clients explicitly load that CA and verify the server; no global trust store changes are made. Leaf certificates are valid for 30 days and include localhost/127.0.0.1. Private key files are mode 0600 in a mode 0700 directory.

The aMQTT broker intentionally permits anonymous **loopback lab** clients. It does not bind a broker credential or topic to the oneM2M `fr` actor. ACME's HTTPS endpoint does not require a client certificate. Consequently the prototype does **not** claim authenticated device identity, protection against a malicious local process, a production-ready security boundary, or encrypted inter-CSE HTTP in the multi-site profile. Do not expose these listeners through a tunnel or change their bind address for a deployment. A network deployment needs authenticated clients plus verified identity-to-origin/topic authorization, and its own acceptance tests.

In ACME's configuration, `http.security.verifyCertificate=false` controls whether the server requires *client* certificates. It does not disable the openSoom client's certificate validation. The CSE's outbound MQTT connection sets `mqtt.security.verifyCertificate=true` and loads the project CA.

## Native behavior and limits

- A normal group `/fopt` query returns per-member CSE results. With ACME 2026.5.3, a member becoming unauthorized causes a top-level 4103; the CSE does not return a mixed aggregate for that case. The smoke captures that error and separately verifies permitted/denied members. Treat a failed aggregate conservatively. Group success still does not establish device execution or ACK.
- The smoke instantiates ACME's bundled `cod:aiQSr` air-quality model, discovers it, and checks rejection of an invalid `pm25` type. This proves model/type handling. Full standard unit mapping, application use, and cross-vendor semantic interoperability need their separate evidence.
- The matching [TS-0023 v5.6.0 airQualitySensor definition](https://specifications.onem2m.org/ts/ts-0023/v5.6.0/5.3/#5316-airqualitysensor) uses integer µg/m³ for `pm25` and float **mg/m³** for `co2`. A raw ppm value must not be assigned to that standard `co2` field. `airFlow.speed` represents a speed level, not measured exhaust volume flow.
- Selective announcements share chosen resources/attributes. They do not copy all state, implement failover, or establish serving-CSE handover.
- These CSEs run as separate processes on one host. The multi-site profile proves native registration/routing/access/announcement behavior, not physical geographic distribution, ETSI MEC hosting, MEC services, or an application continuity result.

## Dependency provenance

ACME CSE retains its **BSD-3-Clause** license; aMQTT retains its **MIT** license. Their installed distributions contain the original license files. openSoom's project license does not replace third-party licenses. HTTPX is 0.28.1; paho-mqtt is 2.2.0. Exact runtime dependencies are pinned in this directory.

Primary references: [ACME source and license](https://github.com/ankraft/ACME-oneM2M-CSE), [pinned ACME release](https://pypi.org/project/acmecse/2026.5.3/), [ACME HTTP configuration](https://acmecse.net/setup/Configuration-http/), [MQTT configuration](https://acmecse.net/setup/Configuration-mqtt/), [native MQTT operation](https://acmecse.net/setup/Operation-mqtt/), [aMQTT 0.12.2](https://pypi.org/project/amqtt/0.12.2/). Matching installed source was checked for the behavior described above; a later upstream release may differ.

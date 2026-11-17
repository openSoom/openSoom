# First implementation scenario and contracts

This is the stage-0 implementation specification. Profiles and physical data are simulated and do not prescribe certified ventilation rates. The two example facilities share the same service, policy, adapter interface and tools.

## Scenario

`food-a` has cooking, washing and packing zones. Its virtual cooking fan can report running while a partly closed damper produces insufficient flow. The manager must distinguish the fan status from the flow observation, check freshness, request an authorized damper change, inspect a separate device acknowledgement and require two fresh later samples before declaring recovery.

`learning-b` uses a classroom, meeting room and shared lounge, with a different profile and vendor wire format. The core has no school/kitchen-specific branches. Profile files define each zone's simulation targets and recovery conditions. [Machine-readable cases](../scenarios/scenarios.json) include normal, exhaust fault, stale data, missing airflow, missing ACK and no recovery.

## Canonical observation

Observation identifies facility and zone, adapter, observed/received timestamps with timezone, simulated provenance, PM2.5 in µg/m³, CO₂ in ppm, airflow in m³/h, a boolean fan report and a damper percentage. Missing values remain null. More than five seconds in the future, expired evidence or missing required measurements cannot justify actuation. JSON schema validates profiles and Pydantic validates observations/actions.

Vendor A uses the canonical field names and units. Vendor B uses dust in mg/m³, airflow in litres/second, `RUN`/`STOP` and a 0–1 valve fraction; the adapter converts to the canonical contract. Validation proves equivalent values through both mappings.

## Resource and application boundaries

The initial actual ACME CSE hosts the openSoom AE, independent adapter/diagnostic/operator/maintenance/observer AEs, two facility containers and per-zone observation/command/ACK containers. A native subscription reports new observations. A native group under the AE performs fan-out over the facility's observation containers. ACPs distinguish permitted actors and an observer limited to the first facility. Resource paths are derived from validated configured identities.

CSE observations are re-read before diagnosis or control. A notification is a hint that must be corroborated with CSE state. SQLite holds incident/run state and a read cache; it does not substitute for the CSE. The initial loopback CSE trusts local callers' origin headers; the service maps bearer tokens to fixed actors, and secure transport/native protocol verification is a separate milestone. Do not claim that an origin header is cryptographic authentication.

## State and control

An incident proceeds from open to recovering to resolved. A command proceeds from requested to acknowledged to verified; missing ACK expires as timed_out, and a maintenance record leaves the ventilation incident unresolved. Idempotency keys cannot be reused with different action arguments. Command expiry, facility, zone, activated profile and actor scope are enforced before execution. The virtual adapter reads the actual CSE command before sending a separate ACK. Two healthy samples after that ACK are required for recovery. The virtual actuator reports the acknowledged requested percentage, including 0 and 50. For an applied setpoint, its deterministic test flow is 1.15 × target × percentage / 100; the no-recovery scenario caps it at 0.4 × target. This is a test fixture, not a physical airflow equation. Partial or closed requests cannot inherit a full-open recovery.

Scenario reset archives the previous incident with an explicit reset reason; it must not produce a recovery claim. Shared live-LLM test limits are defined in [the budget configuration](../config/live-test-budget.json): all workers/retries/resumes use persistent accounting. This is separate from the Codex Goal's budget.

## Initial runtime

Use Python 3.12 and `uv sync` with the tracked lockfile. `uv run opensoom validate` checks bundled profiles; `uv run opensoom doctor` checks runtime/CSE readiness. `scripts/cse_runtime.py` manages the pinned ACME distribution independently of the application environment. `uv run opensoom start` serves the local dashboard/API at loopback port 8090; stop/restart/cleanup are project-scoped. These paths require actual execution checks before release.

The dashboard and both agent clients use the same operations service. The Codex plugin's runtime registration is separate from the actual host workflow test. Model API and external MEC access must be tested before any corresponding success claim. Source versions and actual CSE tests are recorded in `evidence/runtime/`.

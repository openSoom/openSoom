# Reuse a profile or add an adapter

The prototype ships two virtual profiles and two vendor formats. Facility managers use the Codex setup skill to understand and validate configuration. A maintainer still installs system prerequisites and integrates a new physical protocol. Physical adapters are not yet shipped.

## Configure a new site from the plugin

A manager can ask Codex, “Draft a virtual archive-workshop with receiving and conservation benches. Use the learning-space operating policy and vendor-b. My simulated airflow targets are 410 and 560 m³/h, particle warnings 22 and 18 µg/m³, CO₂ warnings 920 and 870 ppm. Bind the conservation damper bench-extract to its independent sensor bench-shaft.” Supply that site's settling time, freshness and position tolerance if enabling maintenance. Request a preview with `draft_facility`; check the displayed policy, zone values, bindings and version. The site's already configured administrator calls `activate_facility` for that exact version. The operating plugin can then discover the new site and test its second zone immediately. Repeating the activation preserves its operating history. Profiles and bindings survive an operations-service restart.

The shipped plugin was exercised over stdio against the real CSE with these two virtual zones. An out-of-zone mapping and an operator's activation attempt were refused. After restart the same version and original CIN were read back, and a new stale-observation trial wrote zero commands. This was a scripted manager/administrator exercise. [Actual receipts](../evidence/agent/facility-onboarding.json) · [Reproduction driver](../scripts/facility_pack_acceptance.py)

Administrator activation also returns `worker_templates` for the maintenance and bridge roles when the approved facility enables maintenance. Each template contains the registered non-administrator `origin`, `facility_id`, `facility_path`, zone-to-asset/sensor bindings and the commissioned settling, freshness and tolerance settings. These are resource identities and configuration, not credentials. An administrator still supplies the deployment endpoint, transport authentication and `bridge_mode` (`local` or the separately configured `mec046` service). Tokens, provider configuration and permission grants are not copied into the activation response. Repeating activation recovers the same settings after restart.

### Reproduce worker reuse on the new site

With the project's pinned Python environment and ACME runtime already installed, run:

```sh
uv run --no-sync python scripts/facility_worker_acceptance.py \
  --output evidence/agent/facility-worker-generalization.json
```

This account-free driver creates a temporary CSE on an ephemeral loopback port and stops it afterward. It activates the workshop pack through the original operational code, restarts that core against its existing database, and launches the shipped `opensoom.maintenance_worker` CLI as separate maintenance and bridge processes with the exported settings. It does not contact the existing demo, a hosted model API or a MEC platform.

The [captured run](../evidence/agent/facility-worker-generalization.json) compares `food-a/cook` at 900 m³/h with the new workshop's **second zone**, `conservation`, at 560 m³/h. The latter binds `bench-extract` to `bench-shaft`. Two post-ACK observations of 600 m³/h with excessive simulated particles leave the incident unresolved without requesting a shaft measurement. A later 515 m³/h observation triggers the additional investigation. An independently injected 35% sensor CIN against an 80% command changes the existing order to actuator/feedback inspection. After a new 95% command, an independent 93% sample changes the **same logical work order** to airflow-path inspection; the old 35% record remains immutable. The incident still needs physical investigation and remains unresolved in the virtual test.

Both facilities use the same worker code. Eight native ACP denials cover cross-facility reads and wrong-role writes; the neighboring zone and the first facility's resource state tags remain unchanged while the new facility operates. This is scripted virtual commissioning with an actual oneM2M CSE and local independent-sample bridge. The sensor values are separately supplied test inputs, not physical measurements or proof of MEC service use. The original MCP onboarding and hosted-model evidence remain separate.

## Provision from configuration files

1. Choose an existing profile or copy one JSON file in `profiles/`. Give a new profile a unique ID and define its zones, targets, freshness window, allowed actions and recovery sample count. Values are simulation inputs until separately validated for a real facility.
2. Add an entry in `config/facilities.json` with a unique facility ID, display name, profile ID, `vendor-a` or `vendor-b`, and any `read_only_roles`. The observer has access only where explicitly listed.
3. Run `uv run --no-sync opensoom validate`, then restart the service. `OPENSOOM_FACILITY_IDS` can select a subset for a small installation. Unknown or duplicate IDs fail validation.
4. Ask Codex to `prepare_setup` for the profile, discover its configured facility and inspect current observations. The ordinary operator cannot activate configuration as an administrator. `apply_setup` validates the requested existing profile and idempotently reapplies its configured facilities only with the administrator identity.
5. Run the same fixture and failure scenarios with the new facility ID, check units/freshness and inspect the resulting command/ACK/observations. Do not substitute a visual for execution evidence.

A third virtual bakery can use `food-production` with `vendor-b`; the diagnosis, actions and tools are unchanged. `tests/test_facility_registry.py` checks this configuration boundary. Each facility's role scope comes from the registry rather than school-specific code.

## Add a vendor mapping

Implement normalization in `src/opensoom/adapters.py`, preserving explicit missing values and observed timestamps. Extend the registry schema's supported adapter list. Test a fixed measurement set through both old and new formats, including unit scaling, boolean/enum handling, missing fields, invalid values and timezones. A new vendor should not require changes to `policy.py` or MCP tool names.

The virtual encoder is for repeatable tests. A real adapter additionally needs authenticated transport, device identity/capabilities, read-only initial operation, command/ACK correlation, timeout behavior and a validated facility control policy. Do not mark it supported on the strength of simulated payload tests.

## Contribute a scenario or standard mapping

Add explicit expected behavior to `scenarios/scenarios.json` and a reproducible check. Recovery requires a distinct ACK and fresh later observations. A scenario that expects refusal can pass its test while the facility remains unresolved.

For a standard projection, document specification version, resource type, identifier, property type and units, then demonstrate native discovery and an application reading it. Preserve raw values and their provenance. Follow the existing [PM2.5 mapping](standard-model.md) and never copy CO₂ ppm into a mass-concentration field.

## Reproduction scope

The verified installation is a source checkout on macOS with Python 3.12. The application uses repository-relative configuration and assets, so a bare wheel without those files is not a supported installation. A distributable package, desktop wizard, authenticated network deployment and physical commissioning require additional work and their own acceptance evidence.

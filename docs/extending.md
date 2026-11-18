# Reuse a profile or add an adapter

The prototype ships two virtual profiles and two vendor formats. Facility managers use the Codex setup skill to understand and validate configuration. A maintainer still installs system prerequisites and integrates a new physical protocol. Physical adapters are not yet shipped.

## Configure a new site from the plugin

A manager can ask Codex, “Draft a virtual archive-workshop with receiving and conservation benches. Use the learning-space operating policy and vendor-b. My simulated airflow targets are 410 and 560 m³/h, particle warnings 22 and 18 µg/m³, CO₂ warnings 920 and 870 ppm. Bind the conservation damper bench-extract to its independent sensor bench-shaft.” Supply that site's settling time, freshness and position tolerance if enabling maintenance. Request a preview with `draft_facility`; check the displayed policy, zone values, bindings and version. The site's already configured administrator calls `activate_facility` for that exact version. The operating plugin can then discover the new site and test its second zone immediately. Repeating the activation preserves its operating history. Profiles and bindings survive an operations-service restart.

The shipped plugin was exercised over stdio against the real CSE with these two virtual zones. An out-of-zone mapping and an operator's activation attempt were refused. After restart the same version and original CIN were read back, and a new stale-observation trial wrote zero commands. This was a scripted manager/administrator exercise. [Actual receipts](../evidence/agent/facility-onboarding.json) · [Reproduction driver](../scripts/facility_pack_acceptance.py)

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

# Reuse a profile or add an adapter

The prototype ships two virtual profiles and two vendor formats. Facility managers use the Codex setup skill to understand and validate configuration. A maintainer still installs system prerequisites and integrates a new physical protocol. Physical adapters are not yet shipped.

## Add a virtual facility without changing application code

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

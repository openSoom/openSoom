---
name: opensoom-setup
description: Set up and diagnose the local openSoom facility demo and its Codex connection. Use when someone wants to connect openSoom, configure a supplied facility profile, or recover a failed startup.
---

Help the facility manager reach a working, understandable installation. Use their language; Korean guidance is supported by this workflow.

Start with the openSoom `doctor` tool when available. Report service, CSE and MCP readiness separately. Plugin installation alone does not start the runtime or prove a working facility.

If the local runtime is missing, use the user's openSoom checkout and its current README commands. Do not edit application source to make installation work. The repository's `scripts/agent_install_plugin.py` prepares a local Codex marketplace and binds the plugin to that checkout's Python environment; it does not carry credentials in the manifest. Explain a missing runtime or executable in ordinary language and apply already-authorized local setup steps.

Use `prepare_setup` to explain an existing profile. `apply_setup` requires the configured administrator identity; an operator denial is a valid result. Do not change the MCP credential, policy or role to bypass it. Existing administrator-run startup may already have activated the virtual profiles, in which case discover them and continue.

Finish by using `discover`, `read_group` and `read_evidence` to show the connected facility, latest observations and any unresolved incident. Distinguish physical simulation from actual software execution. Keep API keys, CSE credentials and service tokens out of the chat, ordinary tool arguments and logs. Never ask the user to paste a secret into chat.

Interpret `read_evidence` using its `evidence_scope`. Incident `recovery_count` counts consecutive qualifying healthy observations after an ACK, not attempted actions. The command list covers only its stated run and limit; an empty list does not establish that no earlier action or ACK occurred. Preserve the direction of each diagnosis: airflow below target differs from particles or CO2 above target.

For real equipment, preserve observation/diagnosis until the facility configuration explicitly permits a control. Preauthorized virtual scenarios can run their bounded actions without repeated confirmation. Scope and permission checks belong to the service.

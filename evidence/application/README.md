# Reproducing application acceptance

From the repository root, with the secure CSE/broker and application on 8090 running from the intended source checkpoint:

```sh
.venv/bin/python scripts/application_acceptance.py
```

The default facility is `learning-b`; `food-a` is read for second-profile/adapter evidence without changing its scenario. The script executes six preauthorized virtual scenarios through the actual application API. It checks real oneM2M discovery, group success, a denied group member with the application's separate diagnostic fallback, registered-AE access denials, standard PM2.5 model discovery/readback, and correlated product MQTT/TLS and HTTPS traces. Its total time budget is 180 seconds. No model API is called.

`acceptance.json` records the outcome, individual run IDs, request IDs, command/ACK/outcome state and source hashes before/after. A source change during execution invalidates the capture. Restart the application from the source checkpoint before running: matching files on disk alone cannot prove what a previously started process imported.

The partial-group check temporarily assigns one selected facility observation container a cloned ACP that denies only the operational reader, then restores its original ACP in `finally`. The virtual adapter and diagnostic identity retain access. At normal completion, the selected facility remains in the `no_recovery` scenario for inspection; an ACK is explicitly distinguished from recovery.

The standalone topology check is separate:

```sh
.venv/bin/python scripts/cse_product_topology.py
```

It uses facility APIs 8091/8092 and CSEs 8180–8182, preserves application 8090, and writes `evidence/runtime/product-multisite-continuity.json`. Runtime self-checks and fixture outcomes do not replace independent Rubric review, live-LLM evidence, physical-device validation, or stage-gate decisions.

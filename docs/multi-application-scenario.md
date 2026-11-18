# Independent operations and maintenance applications

This supplementary, deterministic scenario runs three separate application processes against an actual ACME 2026.5.3 CSE. It demonstrates how two applications reuse the same equipment event for distinct operating needs. Sensor measurements, damper behavior and acknowledgements are simulated. CSE resource creation, native notifications, group requests, application reads, writes and ACP denials actually execute.

The operations application needs to restore a configured operating condition and check its outcome. The maintenance application needs a persistent inspection task even if the operating condition recovers. Requiring a facility manager to copy events between those applications would lose correlation and require duplicate integration. A single application with two UI views is simpler when both workflows have the same owner and permissions. Separate applications are useful here because maintenance has its own output and cannot issue operating commands.

## Reproduce

From the repository root, prepare the ordinary pinned project environment and CSE runtime as described in the README. The CSE install command does not start or stop an existing CSE:

```sh
python3 scripts/cse_runtime.py install
.venv/bin/python -m pytest tests/test_multiapp.py -q
.venv/bin/python scripts/cse_multiapp_smoke.py
```

The runner starts a new CSE with a private generated configuration and database under an ignored `.runtime/multiapp-*` folder. Its HTTP port and every application callback port are assigned by the operating system. It never uses the ordinary service lifecycle records or configured demo ports. It terminates and waits for only its own child processes on success or failure. No account, model API call, physical equipment or paid service is required. The host must permit loopback listeners and child processes.

The default run writes to `evidence/runtime/multiapp/`. To preserve the published film receipts, choose a fresh output path:

```sh
.venv/bin/python scripts/cse_multiapp_smoke.py --evidence tmp/multiapp-reproduction
```

Expected final result: `PASS_ACTUAL_CSE_MULTI_APPLICATION`. The index lists the run ID, source hashes before and after execution, scenario results, artifact hashes, preserved existing process records and cleanup results. Failure leaves a partial index with `FAIL_INCOMPLETE`; it does not become a pass.

## Two consumers of one event

For each case, the runner provisions unique AEs for `operations`, `maintenance` and `device`, then launches one `python -m opensoom.multiapp --role ...` process for each. An additional outsider AE is used only for denied-read checks. The administrative runner provisions resources, ACPs, group membership and subscriptions. Each worker makes CSE requests using only its assigned non-administrator origin. The workers never call one another or use the main dashboard/service as a proxy.

1. The virtual device publishes a nominal wash-zone observation and a cooking-line observation with low airflow and elevated PM2.5. Both include a shared `event_id`, asset identity and the existing `Observation` schema. The example uses the bundled food-production profile; these targets are simulation inputs.
2. The CSE sends two native notifications for the same cooking-line contentInstance, one to each application's own callback. `enc.net=[3]` and `enc.chty=[4]` select contentInstance creation. Each application treats the notification as a hint and retrieves that exact CIN from the configured CSE parent under its own origin. The retained results prove the same source `ri` and different application request IDs.
3. Operations uses native `/fopt` to obtain the configured zone group's results and checks fresh latest observations for both zones. It writes a profile-scoped, expiring `set_damper` command to the CSE. The virtual device receives a native command notification, retrieves the command and independently validates simulation permission, facility, zone, asset, active profile version, action and expiry.
4. Maintenance independently opens an `inspection_required` work order in its own CSE container from the same source CIN. It recommends inspection of the fan, damper and capture path according to the facility's procedure. It does not infer capture adequacy from PM/CO2 or close a physical inspection because simulated values improve.
5. Operations consumes the device's CSE ACK and requires two consecutive fresh post-ACK observations meeting the selected profile before recording `verified_recovery`. Acknowledgement alone remains `awaiting_outcome`. Distinct subscriptions may arrive in different orders, so corroborated observations can wait for the matching ACK. Duplicate CIN notifications cannot create duplicate commands or work orders in a running worker.

The shared implementation module is a library and process entry point. Each role owns its CSE client, notification endpoint, durable local checkpoint, behavior and output container. The main openSoom dashboard and LLM runner retain their existing flow; this isolated scenario is separate execution evidence, not a claim that those interfaces orchestrate these workers.

## Resource and permission contract

Each case has a unique root under `cse-multiapp/multiapp-<event_id>`:

| Resource | Writer | Consumers / purpose |
| --- | --- | --- |
| `observations_cook`, `observations_wash` | Device AE | Operations and maintenance read the common data |
| `zone-observations/fopt` | Provisioned membership | Operations requests native multi-zone context |
| `commands` | Operations AE | Device consumes commands; maintenance cannot create commands |
| `acks` | Device AE | Operations correlates command execution acknowledgement |
| `operations_reports` | Operations AE | Persistent incident/control/outcome transitions |
| `work_orders` | Maintenance AE | Persistent, independently meaningful inspection work |

Streams have explicit ACPs. Application writes are CREATE only, restricted to child type 4 through `acod.chty=[4]`; workers cannot create subscriptions or change ACPs. The provisioner has administrative access. The runner checks actual `4103` responses for maintenance control, maintenance observation forgery, operations work-order writes, maintenance operations-report writes, device subscription creation, and outsider observation reads. Successful writes/readback use the respective application origin.

The loopback deployment trusts processes to claim their AE origin in `X-M2M-Origin`. These ACP tests prove CSE permission enforcement for the asserted origins, not cryptographic AE identity binding. The repository's separate HTTPS/MQTT-TLS evidence does not change the trust boundary of this HTTP example.

## Captured cases and evidence

| Case | Operations output | Independent maintenance output |
| --- | --- | --- |
| `recovery` | `verified_recovery`, one ACK and two later nominal samples | `observations_recovered_inspection_pending`; inspection remains open |
| `missing_ack` | `ack_timed_out`; CSE command creation succeeded but device emitted no ACK | `inspection_required` from the same fault observation |
| `no_recovery` | `unresolved_after_ack`; device ACK exists but two later samples still violate the profile | `inspection_required`; no recovery claim |

The [filmed run](../evidence/runtime/multiapp/index.json) is `ma-d1a54f066e`. After a review found that an intervening invalid observation needed to reset the consecutive-sample count, the [corrected run](../evidence/runtime/multiapp-revalidation/index.json) repeated all three cases on the updated source as `ma-b9129cb90a`. The indices retain separate tool and artifact hashes. Each case directory contains:

- `result.json`: AE registration results, ACP definitions, subscriptions, source-event correlation, distinct process IDs, CSE readback and denial responses.
- `<role>-requests.jsonl`: the complete sanitized CSE request/response trace for each worker, with timestamps and request IDs. Every request uses that worker's origin; none uses `CAdmin`.
- `<role>-state.json`: notification verification and delivery receipts, authoritative source reads, command/ACK correlation, meaningful transitions and the final stopped checkpoint.

The runner asserts one command per case, zero ACKs in `missing_ack`, one ACK in the other cases, expected operation/work-order results, empty worker error lists and distinct worker PIDs. Unit tests additionally cover expired/wrong-scope/disabled control, source scope validation, wrong ACK correlation, pre-ACK/stale data, consecutive recovery samples and reordered ACK notification delivery.

This evidence is not a physical ventilation experiment, certified protection result, multi-host deployment, MEC integration, handover, or live-model execution. Independent rubric review must assess the official criterion descriptor against this particular scope; a successful scenario run does not itself award an Expert score.

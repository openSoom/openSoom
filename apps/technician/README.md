# Technician workbench

A technician uses this facility-specific web application to decide which inspection to schedule, record a field check, and pass a disposition back to the facility operator. It reads work orders authored by the maintenance AE. The operator continues to verify recovery against measured airflow.

From the repository root, after [installing openSoom and ACME](../../README.md#which-inspection-comes-first), run the local lab.

```sh
uv run --no-sync python scripts/maintenance_demo.py --dashboard-port 19490 --technician-port 19492 --hold
```

Open the [technician workbench](http://127.0.0.1:19492/) or follow a work order from the [operator console](http://127.0.0.1:19490/). Choose the order, inspect its source measurements, then select a field activity and save it. The operator sees the disposition for the current recommendation. The technician can read their site's field notes again after the web process restarts. A link ending in `/?order=work-…` selects that site's exact order.

| Component | Runs here | Reads and writes |
| --- | --- | --- |
| Technician browser | Local browser, same-origin HttpOnly session | Uses the working queue and inspection endpoints |
| Technician service | Separate loopback ASGI process, one commissioned facility | Reads work-order and ACK CINs through its own bound TLS gateway credential. Writes separate immutable inspection records. |
| MEC maintenance and sensor bridge | Independent application processes, separate AEs | Publish work orders and independent measurements under their respective policies |
| Site operations | Facility operating service | Creates equipment commands, judges recovery and reads the current revision's field disposition |

The technician session in this local demonstration is granted to a browser on the same machine. The ASGI service requires a loopback peer and host, and same-origin writes. A deployed site needs its own operator identity and user authentication. Keep the device-control service, worker gateway and their credentials separate.

## What an entry records

`GET /api/work-orders` returns the configured facility queue. A new work-order CIN carries the airflow target captured with its source outcome. For an older CIN, the workbench explicitly labels the current installation's configured target. When a newer command supersedes the displayed evidence, the workbench waits for a current recommendation.

`POST /api/work-orders/{order_id}/inspections` takes the reviewed work-order CIN ID, a stable UUID, one of `scheduled`, `checked` or `escalated`, and an optional note. The service validates the order against its current facility queue. The technician's private `inspection_notes` CIN retains the note. The public-to-operations `inspections` CIN contains the activity and its exact order reference. Retrying identical input returns the same entry. A conflicting request ID or superseded revision returns HTTP 409. If interrupted between the two writes, retrying the same request completes the disposition from the retained private record.

The technician AE cannot write commands, sensor responses or the maintenance app's work order. The site operator can read the disposition through oneM2M. In the operations API, the same-site observer sees facility measurements but no work orders. The maintenance role sees its orders without the technician’s disposition. Neither the operator AE nor the MEC maintenance AE can read the private note. [Native runtime and restart checks](../../evidence/runtime/technician-workbench.json)

## What happens after a field check?

Saving **Inspection performed** records the technician’s activity against the order revision they actually reviewed. Operating recovery needs the facility’s configured number of consecutive qualifying measurements after the same device ACK. The site writes that outcome to its MN-CSE. The maintenance worker then reads the original ACK and observation CINs and puts their identifiers, readings, and timestamps on a new revision of the **same open work order**. Earlier field entries retain their original evidence. The operator and technician can both inspect the recovery revision.

Replay this path on a temporary local CSE with virtual equipment. The trial also pauses the maintenance worker across operating recovery and delivers a late position-sensor reply before restarting the worker.

```sh
uv run --no-sync python scripts/field_recovery_acceptance.py --output .runtime/field-recovery.json
```

The normal loopback technician HTTP interface is exercised with an automated ASGI client in this trial. The independent readback requires the original records to remain in the site CSE until the worker verifies them. [Recorded trial](../../evidence/runtime/field-recovery.json)

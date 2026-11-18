# openSoom maintenance applications

The maintenance AE opens one inspection order when a facility incident occurs. If a device accepts a command but measured airflow stays below the site's configured target, this AE requests independent shaft position. The bridge resolves the site's sensor binding and returns the measurement through its own oneM2M identity. Only the maintenance AE can change inspection priority. A failed lookup leaves the existing order open with unknown evidence.

## Run a local incident

From the repository root, run the [isolated maintenance demo](../../scripts/maintenance_demo.py) with the project Python environment. It starts a real MN-CSE, an IN-CSE, a device simulation and both application processes. The independent position sensor in this mode is a second virtual device publishing to the MN-CSE. The command and follow-up measurements use the facility profile in [facilities.json](../../config/facilities.json).

```bash
.venv/bin/python scripts/maintenance_demo.py --hold
```

## Deploy a facility's workers

Build one image and record its registry digest. Give each role a different provisioned AE identity, its own CSE gateway token and a private callback address. The gateway authenticates the bearer and binds it to the AE origin. The site's MN-CSE enforces resource privileges. Its upstream binding must only be available to trusted workloads. Apply network policy so the workers can reach the gateway, DNS and their approved service endpoints.

```bash
docker build --platform linux/amd64 -f apps/mec-maintenance/Dockerfile -t opensoom-maintenance:local .
```

Place nonsecret role settings in two JSON files. Set `origin` to the actual AE-ID returned by your CSE for that facility. The `facility_path` starts with its CSE base name. Set `cse_ca` to a trusted CA bundle inside the container. Keep provider credentials on the bridge only. The local demo provisions the same scoped resource tree and authentication mechanism.

```json
{
  "facility_id": "food-a",
  "facility_path": "cse-mn/opensoom/facilities/food-a",
  "origin": "REPLACE_WITH_MAINTENANCE_AE_ID",
  "cse_url": "https://os-gateway.opensoom-workers.svc.cluster.local:8443",
  "cse_ca": "/etc/opensoom/trust/ca.crt",
  "assets": {"cook": {"asset_id": "extract-damper-01", "sensor_id": "shaft-position-01"}},
  "freshness_seconds": 45,
  "settle_seconds": 3,
  "tolerance_pct": 10,
  "poll_seconds": 5
}
```

In the bridge's copy, use its own `origin`. Add `bridge_mode` with value `local` to consume a facility-scoped `independent_samples` CIN. To consume a separate provider, use `mec046` and configure these additional fields. Replace the illustrative names and resource ID with the deployment's registered endpoint and mapped sensor. The bridge checks the advertised authority against `allowed_service_origins` before any request. A bearer-protected service requires HTTPS.

```json
{
  "bridge_mode": "mec046",
  "registry_url": "http://mec-ingress/mec_service_mgmt/v1/services",
  "allowed_service_origins": ["http://mec-ingress"],
  "sensor_type": "FLX",
  "provider_sensor_ids": {"shaft-position-01": "REPLACE_WITH_PROVIDER_FCNT_RI"}
}
```

The bridge looks up the active SSS category in MEC 011, discovers the mapped sensor in MEC 046, then reads its data. It records the service and sensor IDs, response status and SHA-256 of the provider response. The STF_685 implementation serves `/queries/sensor_data` under the registered `sens/v1` endpoint. For an FCNT provider it returns an encoded array of characteristics. The `sample` attribute carries the independent virtual encoder's original facility, zone, asset, logical sensor ID, UTC measurement time, unit, value and source. A scalar provider can instead supply its own MEC 046 `dataTimestamp` and `dataUnitOfMeasure`. Processing never derives a measurement time from receipt time. [ETSI Sensor Sharing implementation](https://labs.etsi.org/rep/mec/etsi-mec-sandbox/-/tree/STF_685/go-apps/meep-sss)

### Commission an external sensor provider

A site may require the bridge to verify that its independent provider is commissioned before checking shaft position. Enable this by setting `provider_registration.profile` and `provider_registration.record` in the bridge configuration. The record is a site-administered MEC 033 `IotPlatformInfo` with an approved ID, message transport and independent oneM2M endpoint. A tested registration shape is in [the private deployment example](../../deploy/mec-sandbox/commission.py). Add the same profile alias to the site's `maintenance.provider_profiles` and subscribe the bridge to the site's `provider_requests`. Restrict commissioning to this preapproved registration.

```bash
.venv/bin/python scripts/commission_provider.py --service http://127.0.0.1:8090 \
  --runtime .runtime --facility food-a --profile independent-shaft-provider \
  --request-id enroll-independent-shaft
```

The authenticated site administrator issues an immutable oneM2M request using a profile alias. The bridge discovers MEC 033 via MEC 011 and reads the registered platform. For an absent record it submits the configured registration, then reads it back. For an existing disabled record it requests enablement and verifies the updated registration. A transport mismatch or unconfirmed state leaves the provider unavailable. The bridge writes a scoped response to the MN-CSE, and the operator client rereads it. Repeating the same request ID recovers the original receipt. For configured sites every MEC 046 lookup checks the current MEC 033 registration first. The status of a virtual device and that of its owning provider are independently observable.

In the approved profile, set `sensor_test_callback` to the bridge's private service address ending in `/mec046/test`. One active bridge owns this callback for the installation. The site administrator's oneM2M commissioning request then configures the 046 service as well. The bridge checks the 046 subscription list, creates a missing slot with a reachability test, correlates the incoming test to the returned location, and verifies the stored subscription. After a restart the bridge rediscovers the existing slot. The facility tool accepts the installed profile alias. Its arguments contain no callback address.

The pinned Sandbox returns subscription self links under `/subscriptions/sensor_data/{id}` and serves individual GET and DELETE under `/queries/sensor_data/{id}`. Its implemented `TestNotification` confirms callback delivery. The independent position value comes from a subsequent sensor-data GET. The cloud capture includes the platform's sender log, the original oneM2M receipts and the empty subscription list after cleanup. [Managed 033 and 046 execution](../../evidence/runtime/option-c/commissioned-sensor-roundtrip.json)

### ETSI Sandbox Option C

Export the intended `dep-opt-c` scenario as JSON. Use its actual EDGE location and the process name of the MN-CSE already hosted there. The renderer adds two EDGE-APP entries with independent instance IDs and an explicit dependency on that MN-CSE. It preserves other processes. The deployment administrator injects the scoped credentials and CA mount through the deployment's chart configuration. The scenario environment field carries only nonsecret worker settings.

```bash
python3 apps/mec-maintenance/deployment.py --scenario dep-opt-c.json --edge "$EDGE" \
  --mn-process "$MN_PROCESS" --image "$IMAGE_DIGEST" \
  --maintenance maintenance.json --bridge bridge.json > private-scenario.json
```

Deploy the exported scenario with your Sandbox and record the resulting instance, host and image identifiers. A rendered JSON file only establishes the requested topology. Confirm callbacks from the actual MN-CSE and the worker's complete service lookup before using it as deployment evidence.

### Private Kubernetes service test

Create the target namespace, an `os-worker-trust` ConfigMap containing `ca.crt`, and independent `os-maintenance-credentials` and `os-bridge-credentials` Secrets with their `cse-token` values. The bridge Secret can also supply `mec-token` for a protected provider. The renderer creates ClusterIP services and two separate unprivileged deployments. Their Kubernetes service-account token is disabled. Kubernetes execution can be tested independently of the Sandbox placement engine.

```bash
python3 apps/mec-maintenance/deployment.py --namespace opensoom-workers --image "$IMAGE_DIGEST" \
  --maintenance maintenance.json --bridge bridge.json > private-workers.json
kubectl apply -f private-workers.json
```

Have the site owner register `outcomes` and `sensor_responses` subscriptions to the maintenance service's `/notify`, and `sensor_requests` to the bridge's `/notify`. Supply `OPENSOOM_WORKER_CALLBACKS` to the core at provisioning time or register the native subscriptions with the facility administrator. Both apps reconcile existing CINs at startup and periodically. A callback only wakes a scoped re-read. The operator's dashboard projects work-order revisions from CSE resource IDs.

## Verify the decision with the maintenance AE

Given the run ID returned by the site's demo or scenario API, use the installed maintenance credentials to retrieve the original observation, source outcome, request and response CINs, and all three work-order stages. For a commissioned installation, add `--commission-id` with the owner request ID. The capture checks that the trusted provider and sensor service have different MEC instance IDs and that both resolve to this work order. No administrator credential is needed for this reread.

```bash
kubectl -n opensoom-workers exec -i deployment/os-maintenance -- \
  python - --run-id "$RUN_ID" --commission-id "$REQUEST_ID" \
  < scripts/capture_maintenance_order.py
```

The [two-service cloud capture](../../evidence/runtime/mec-provider-commissioning.json) includes the denied setup attempts, the provider's 404 → 201 → 200 transition and the revised order. The [local run](../../evidence/runtime/maintenance-release-local.json) shows how a site with its own independent sensor makes the same maintenance decision through oneM2M.

# Run the managed Option C demonstration

A maintenance technician receives an unresolved ventilation work order. A separate provider publishes mechanical shaft position to its own ACME CSE. The operator's bridge discovers ETSI MEC 033 and 046 services, commissions the provider and reads the fresh position. The same work order gains an actuator-feedback inspection priority. The trial used virtual equipment, a 100% command and an independently generated 35% position. The work order remained open.

The Sandbox created two applications on each of two logical edges. One runs the site's real MN-CSE. The other runs the actual maintenance image. A platform-wide 011 registry, 033 and 046 service, central IN-CSE, separate provider CSE and private service bridge complete the test topology. The maintenance worker and MN-CSE run on the chosen logical edge. The facility's service and bridge retain stable endpoints through a planned re-placement. One physical Kubernetes node hosted both logical locations.

| Operation | Record |
| --- | --- |
| Admission and discovery | Native controller application IDs, ACTIVE 011 records, a 033 provider registration, the 046 sensor query and invalid-sensor response. [Native services](../../evidence/runtime/option-c/native-services.json) |
| Configure both services from oneM2M | An open work order waited for an unregistered provider. A facility owner commissioned 033 and created a native 046 sensor subscription. The service tested the bridge callback. A bridge restart reused the same slot. A fresh sensor query revised the existing order. Cleanup removed exactly one slot. [Single-run receipt](../../evidence/runtime/option-c/commissioned-sensor-roundtrip.json) |
| North facility edge | Controller validated the custom topology and its Virt Engine installed two Helm releases. The fresh maintenance case went from revision 2 to revision 4. [Managed north](../../evidence/runtime/option-c/managed-north.json) · [Product case](../../evidence/runtime/option-c/managed-north-product.json) |
| South facility edge | Planned servicing moved the selected logical location. New Pod UIDs, actual Mcc registration and the same CSE work-order resource survived. A second fresh case completed on this placement. [Managed south](../../evidence/runtime/option-c/managed-south.json) · [Product case](../../evidence/runtime/option-c/managed-south-product.json) |
| Terminated maintenance Pod | Kubernetes recreated the deployed worker and its first successful reconciliation was observed in 14.768 seconds. The MN stayed online and returned the same revision-4 contentInstance. [Restart receipt](../../evidence/runtime/option-c/managed-worker-restart.json) |

The operator selects a logical host in the scenario. Both candidates demonstrated eligibility by running the same two images, reaching the same independent provider and completing a fresh case. The ETSI Sandbox controller and virtualization engine perform admission, activation and workload installation. The resource model supplies logical geography. The physical machine, its local durable CSE directory and the IP path are shared. This exercise measures planned application redeployment and a separate Pod-restart case. Geographic latency, physical host failure and autonomous host ranking remain outside its measured scope.

## Component identities

The headless deployment uses the publicly available ETSI Sandbox source at commit `8c66f08e443be174f109fe2ac645247c9afcd449`. MEC 011, 033 and 046 use the original Go servers. The platform and sandbox controllers read the local database credential from a Secret. The scope-limited Virt Engine delegates to Helm 3.10.1 in a precreated namespace. The patches live beside this guide. This lab supplies its own ACME 2026.5.3 MN package through the native platform lifecycle. The organizer's hosted account, stock Annex B web console, OAuth login and stock `dep-opt-c` MN image were outside this execution. [ETSI Sandbox source](https://labs.etsi.org/rep/mec/etsi-mec-sandbox/-/tree/8c66f08e443be174f109fe2ac645247c9afcd449) · [oneM2M TR-0080](https://specifications.onem2m.org/tr/tr-0080/latest/) · [ACME](https://github.com/ankraft/ACME-oneM2M-CSE)

The sensor provider has an ACME administrator distinct from the fixed discovery identity used internally by the upstream 046 client. An explicit ACP grants that identity only discovery and retrieval of the sample. The provider uses a project-defined FCNT with a `sample` attribute. The recorded native 046 response embeds that typed resource's characteristics in its `data` string. Its top-level time and unit are empty. openSoom checks the source observation time, sensor ID, facility, zone, asset, unit and source in the provider's payload. The 046 implementation polls once per minute and supports the first discovered IoT platform per service instance. The bridge checks current 033 enrollment before accepting new readings. Workstation traffic uses SSH, internal MEC traffic uses HTTP, and worker-to-CSE requests pass through a role-bound HTTPS gateway with the private test CA. The MQTT endpoint is part of the 033 transport declaration. The end-to-end sensor measurement in these receipts used the provider's oneM2M HTTP binding.

## Rebuild the lab

Use a dedicated x86-64 Ubuntu VM with Docker, Python 3, curl, OpenSSL and the checkout. A build machine additionally needs Git, a recent Go toolchain and uv. The verified host had 4 GiB of memory and a 30 GB standard disk. Cluster services use ClusterIP. Keep the Kubernetes API on the protected test machine. The supplied systemd setup blocks TCP 6443 on the external uplink and lets Pods reach the API on the private node path.

From the repository root, build the pinned components. Keep test credentials in the ignored build folder.

```bash
export BUILD_DIR="$PWD/.runtime/rebuild-mec"
mkdir -p "$BUILD_DIR"/{services,cse,operations,private}
chmod 700 "$BUILD_DIR/private"
git clone https://labs.etsi.org/rep/mec/etsi-mec-sandbox.git "$BUILD_DIR/etsi"
SOURCE="$BUILD_DIR/etsi" OUTPUT="$BUILD_DIR/services" bash deploy/mec-sandbox/package-services.sh
cp deploy/mec-sandbox/Cse.Dockerfile "$BUILD_DIR/cse/Dockerfile"
cp deploy/cse-requirements.txt deploy/acme-single.ini deploy/mec-sandbox/{cse-entry.py,shaft-position.fcp} "$BUILD_DIR/cse/"
cp deploy/mec-sandbox/Operations.Dockerfile "$BUILD_DIR/operations/Dockerfile"
cp -R src config profiles schemas scenarios web "$BUILD_DIR/operations/"
uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements-txt -o "$BUILD_DIR/operations/requirements.txt"
```

Copy these build contexts and the checkout to the dedicated host if building elsewhere. Execute the following blocks on that host, from the checkout. Set `BUILD_DIR` there to the transferred directory. Build the operations context from the current project revision. Do not transfer private workstation credentials.

```bash
sudo bash deploy/mec-sandbox/prepare-test-host.sh
repo="$PWD"
(cd "$BUILD_DIR/services" && bash "$repo/deploy/mec-sandbox/import-images.sh")
sudo docker build -t opensoom/acme:2026.5.3 "$BUILD_DIR/cse"
sudo docker build -t opensoom/operations:lab "$BUILD_DIR/operations"
sudo docker build -f apps/mec-maintenance/Dockerfile -t opensoom/maintenance:lab .
for image in opensoom/acme:2026.5.3 opensoom/operations:lab opensoom/maintenance:lab; do
  sudo docker save "$image" | sudo k3s ctr images import -
done
for key in opensoom-couchdb opensoom-provider-mqtt; do
  if ! sudo k3s kubectl get secret "$key" >/dev/null 2>&1; then
    openssl rand -hex 32 | tr -d '\n' | sudo k3s kubectl create secret generic "$key" --from-file=password=/dev/stdin
  fi
done
python3 deploy/mec-sandbox/workloads.py | sudo k3s kubectl apply -f -
```

Wait for CoreDNS, Redis, CouchDB and the original ETSI HTTP servers to answer. The controller and 033 APIs can start later than the Kubernetes Pod reports Running. Re-running `commission.py` retrieves existing project records. Use the independent provider's discovered RI to configure the product. The example publishes for 25 minutes. A later live rehearsal needs a fresh bounded provider run.

```bash
lab="$repo/deploy/mec-sandbox"
export RUN_DIR="$BUILD_DIR/private"
cd "$RUN_DIR"
provider_ip=$(sudo k3s kubectl get svc opensoom-provider -o jsonpath='{.spec.clusterIP}')
python3 "$lab/provider.py" "http://$provider_ip:8080/cse-provider" > first-sample.json
python3 "$lab/provider.py" "http://$provider_ip:8080/cse-provider" --cycles 300 > provider-stream.jsonl &
sensor_ri=$(python3 -c 'import json; print(json.load(open("first-sample.json"))["sensor_ri"])')
python3 "$lab/commission.py" apps > admissions.json
python3 "$lab/commission.py" provider-profile > provider-registration.json
python3 "$lab/product-lab.py" --state "$RUN_DIR/auth" --record provider-registration.json \
  --sensor-ri "$sensor_ri" --operations opensoom/operations:lab --worker opensoom/maintenance:lab
sudo k3s kubectl -n opensoom-workers rollout status deploy/os-operations
sudo k3s kubectl -n opensoom-workers exec -i deploy/os-operations -- python - subscribe < "$lab/lab-action.py"
sudo k3s kubectl -n opensoom-workers exec -i deploy/os-operations -- python - start < "$lab/lab-action.py"
```

Record the returned run ID. On a fresh deployment, wait for the operator dashboard to report a pending work order with reason `provider_unregistered`. Send the approved provider profile through oneM2M, then save the returned commissioning request ID. Give the upstream platform up to two 60-second discovery cycles while the provider stream stays active.

```bash
sudo k3s kubectl -n opensoom-workers exec -i deploy/os-operations -- python - commission < "$lab/lab-action.py"
```

The bridge verifies the 033 enrollment and configures one 046 subscription. The provider sends a `TestNotification` to the installed bridge address. A later 046 data query reads the independent virtual encoder position and updates the original work order. Each fresh deployment generates its own resource and request IDs. After the final product capture, the bridge operator can run `subscription-check.py read` or `subscription-check.py remove` inside the bridge Pod to inspect or remove its owned slot. The next authorized commissioning request can recreate it.

```bash
sudo k3s kubectl -n opensoom-workers exec -i deploy/os-maintenance -- python - --run-id "$RUN_ID" --commission-id "$COMMISSION_ID" \
  < "$repo/scripts/capture_maintenance_order.py"
python3 "$lab/capture.py" > native-capture.json
python3 "$lab/stage-chart.py" | sudo k3s kubectl apply -f -
python3 "$lab/stage-mn.py" | sudo k3s kubectl apply -f -
python3 "$lab/placement.py" | sudo k3s kubectl apply -f -
controller_ip=$(sudo k3s kubectl get svc meep-platform-ctrl -o jsonpath='{.spec.clusterIP}')
for side in north south; do
  python3 "$lab/scenario.py" "$side" > "$side.json"
  curl --fail --silent --show-error -H 'Content-Type: application/json' --data-binary "@$side.json" \
    "http://$controller_ip/platform-ctrl/v1/scenarios/inspection-$side"
done
bash "$lab/cutover.sh" north
python3 "$lab/placement-capture.py" north > managed-north.json
```

Run a fresh virtual case with the same `lab-action.py start` command. Read its results with `capture_maintenance_order.py` inside `deploy/os-managed-maintenance`. Repeat on south using `cutover.sh south` and `placement-capture.py south`. The cutover waits for the previous MN Pod to release its database. Both deployments must be Ready, and the same original work-order RI, creation time and contents must be retrievable. `restart-check.py` additionally terminates the managed maintenance Pod and waits for a successful reconciliation. `cutover.sh restore` returns the facility to the original direct deployments. The namespace-scoped Helm service account manages only namespaced release records and Deployments. Its optional upstream cluster-role-binding housekeeping is unavailable in this scoped build. Both tested charts contain only Deployments.

For a stopped existing cloud lab, start the same VM and refresh its SSH endpoint. Check the provider stream, 033 enrollment, 011 catalog, worker health, Mcc registration and the current logical placement. Re-commission in dependency order if transient platform or operations stores were recreated. Preserve the mounted CSE data and the project-local gateway credentials. Stop the VM after the session. The measured setup used Google Compute Engine us-central1, e2-medium, one ephemeral external IPv4 and a 30GB pd-standard disk. At 730 running hours the estimate was US$29.31 before taxes and transfer. The retained disk costs about US$1.20/month while the VM is stopped. [VM pricing](https://cloud.google.com/compute/vm-instance-pricing) · [Disk pricing](https://cloud.google.com/compute/disks-image-pricing) · [IPv4 pricing](https://cloud.google.com/vpc/network-pricing#ipaddress)

#!/usr/bin/env bash
# On the dedicated test VM. Only run after the ordinary cloud fixture is idle.
set -euo pipefail
k=(sudo k3s kubectl)
ns=opensoom-workers
get_ip(){ "${k[@]}" get svc "$1" -o jsonpath='{.spec.clusterIP}'; }
ctrl="http://$(get_ip opensoom-placement-ctrl)/sandbox-ctrl/v1"
mca="http://$(get_ip opensoom-mn):8080/cse-mn"
mkdir -p placement-data
order_path=opensoom/facilities/food-a/work_orders/la
cse_get(){
  curl --fail --silent --show-error --max-time 8 -H 'X-M2M-Origin: CAdmin' \
    -H "X-M2M-RI: os-placement-$(date +%s)" -H 'X-M2M-RVI: 4' "$mca/$1"
}
stop_managed(){
  curl -sS --max-time 12 -X DELETE "$ctrl/active" >placement-data/terminate-response.json || true
  for dep in os-managed-maintenance os-managed-mn; do
    if "${k[@]}" -n "$ns" get deploy "$dep" -o name >/dev/null 2>&1; then
      "${k[@]}" -n "$ns" wait --for=delete "deployment/$dep" --timeout=65s || return 1
    fi
  done
  for selector in 'app=os-managed-mn' 'opensoom.org/placement-owner=sandbox'; do
    if [[ -n "$("${k[@]}" -n "$ns" get pod -l "$selector" -o name)" ]]; then
      "${k[@]}" -n "$ns" wait --for=delete pod -l "$selector" --timeout=90s || return 1
    fi
  done
}
restore_direct(){
  if ! stop_managed; then
    echo 'Native cleanup still active. Direct CSE remains paused to protect its database.' >&2
    return 1
  fi
  "${k[@]}" patch svc opensoom-mn -p '{"spec":{"selector":{"app":"opensoom-mn"}}}' >/dev/null
  "${k[@]}" scale deploy/opensoom-mn --replicas=1 >/dev/null
  "${k[@]}" -n "$ns" scale deploy/os-maintenance --replicas=1 >/dev/null
}
case "${1:-}" in
  north)
    cse_get "$order_path" >placement-data/before.json
    "${k[@]}" -n "$ns" scale deploy/os-maintenance --replicas=0 >/dev/null
    "${k[@]}" scale deploy/opensoom-mn --replicas=0 >/dev/null
    "${k[@]}" wait --for=delete pod -l app=opensoom-mn --timeout=75s
    trap 'restore_direct' ERR
    "${k[@]}" patch svc opensoom-mn -p '{"spec":{"selector":{"app":"opensoom-mn-relay"}}}' >/dev/null
    ;;
  south)
    cse_get "$order_path" >placement-data/before-south.json
    stop_managed
    trap 'restore_direct' ERR
    ;;
  restore)
    restore_direct
    exit
    ;;
  *) echo 'Usage: cutover.sh north|south|restore' >&2; exit 2 ;;
esac
side=$1
status=$(curl --fail --silent --show-error --max-time 22 -o "placement-data/activate-$side.json" -w '%{http_code}' -X POST "$ctrl/active/inspection-$side")
echo "Sandbox activate $side HTTP $status"
# The Sandbox controller returns before the Virt Engine consumes its message.
for i in $(seq 1 65); do
  if "${k[@]}" -n "$ns" get deploy/os-managed-mn deploy/os-managed-maintenance >/dev/null 2>&1; then break; fi
  sleep 1
done
"${k[@]}" -n "$ns" rollout status deploy/os-managed-mn --timeout=90s
"${k[@]}" -n "$ns" rollout status deploy/os-managed-maintenance --timeout=90s
for i in $(seq 1 55); do
  if cse_get "$order_path" >"placement-data/after-$side.json" 2>/dev/null; then break; fi
  sleep 1
done
python3 - "$side" <<'CHECK'
import json,sys
from pathlib import Path
folder=Path("placement-data")
before_name="before-south.json" if sys.argv[1]=="south" else "before.json"
before=json.loads((folder/before_name).read_text())["m2m:cin"]
after=json.loads((folder/("after-"+sys.argv[1]+".json")).read_text())["m2m:cin"]
assert (before["ri"],before["ct"],before["con"]) == (after["ri"],after["ct"],after["con"])
print("Persistent work-order CIN",after["ri"])
CHECK
curl -fsS "$ctrl/applications" >"placement-data/apps-$side.json"
"${k[@]}" -n "$ns" get pods -l opensoom.org/logical-host="$side-edge" -o json >"placement-data/private-pods-$side.json"
echo "Verified $side on the native Sandbox."

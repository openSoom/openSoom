#!/usr/bin/env python3
"""Compare the technician queue's native CSE reads on a controlled, retained history."""
import argparse
import hashlib
import json
import os
import tempfile
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cse_multiapp_smoke import ROOT, start_cse, stop_process
from facility_worker_acceptance import notify_sink
from opensoom.core import Core
from opensoom.maintenance import read_facility_stream
from opensoom.onem2m import CSEClient, CSEError
from opensoom.technician import FieldDesk


class Before(FieldDesk):
    """The previous release's stream reader (91a359e), with the same queue joins."""
    def stream(self, stream):
        path = self.path + "/" + stream
        cnt = self.cse.retrieve(path)["body"]["m2m:cnt"]
        version = (cnt["ri"], cnt["st"])
        saved = self.cache.get(stream)
        if saved and saved[0] == version:
            return saved[1]
        rows = list(read_facility_stream(self.cse, path, cnt["ri"], self.facility))
        self.cache[stream] = version, rows
        return rows


class CountReads(CSEClient):
    def _record(self, event):
        reply = event["response"]
        self.requests.append((reply["rqi"], reply["rsc"], event["query"], len(reply["body"].get("m2m:cnt", {}).get("m2m:cin", []))))


def observe(desk):
    desk.cse.requests = []
    start = time.perf_counter()
    output = desk.queue()
    requests = desk.cse.requests
    return output, {"calls": len(requests), "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                    "first_rqi": requests[0][0], "last_rqi": requests[-1][0],
                    "batch_rows": [size for _, _, query, size in requests if query.get("rcn") == 4]}


def decisions(output):
    # Batch reads intentionally give all members that request's trace ID.
    def strip(item):
        if isinstance(item, dict):
            return {k: strip(v) for k, v in item.items() if k not in ("read_rqi", "ack_rqi")}
        if isinstance(item, list):
            return [strip(v) for v in item]
        return item
    return json.dumps(strip(output), sort_keys=True, separators=(",", ":")).encode()


def run(folder, url, version):
    fid = "food-a"
    admin = CSEClient(url)
    with ExitStack() as stack:
        stack.enter_context(admin)
        sink = notify_sink()
        stack.callback(sink.server_close)
        stack.callback(sink.shutdown)
        env = {"OPENSOOM_CSE_BASE": "cse-multiapp", "OPENSOOM_NOTIFY_URL": f"http://127.0.0.1:{sink.server_port}/notify"}
        with patch.dict(os.environ, env):
            core = Core(runtime=folder/"operations", cse=admin)
            core.bootstrap()
        site = core.facility(fid)
        config = {"facility_id": fid, "facility_path": site["path"], "name": site["name"], "profile": site["profile"],
                  "simulation": True, "zones": {"cook": {"name":"Cooking","target_m3_h":900}}}
        tech = core.identities["technician:" + fid]
        worker = core.identities["maintenance:" + fid]
        old = Before(config, stack.enter_context(CountReads(url, origin=tech)))
        fresh = FieldDesk(config, stack.enter_context(CountReads(url, origin=tech)))

        def put(stream, name, content, origin):
            data = {"m2m:cin": {"rn": name, "cnf": "application/json:0", "con": json.dumps(content)}}
            return admin.create(site["path"]+"/"+stream, 4, data, origin=origin)["body"]["m2m:cin"]

        def order(number):
            work = f"order-{number:03}"
            payload = {"facility_id":fid,"zone_id":"cook","asset_id":"extract-damper-01","incident_id":"incident-"+work,
                       "work_order_id":work,"observed_at":"2026-10-15T00:00:00+00:00","priority":"inspection",
                       "kind":"work_order","revision":1,"command_id":None,"status":"open","target_airflow_m3_h":900}
            return put("work_orders", work, payload, worker)

        def annotation(number, original):
            work = f"order-{number:03}"
            shared = {"facility_id":fid,"work_order_id":work,"work_order_ri":original["ri"],
                      "request_id":f"test-{number}","action":"checked"}
            put("inspection_notes", work, {**shared,"kind":"technician.field_note","note":f"Synthetic fixture {number}"}, tech)
            put("inspections", work, {**shared,"kind":"technician.inspection"}, tech)

        def compare():
            base, left = observe(old)
            actual, right = observe(fresh)
            assert decisions(base) == decisions(actual)
            return {"retained_orders":len(actual["work_orders"]), "semantic_sha256":hashlib.sha256(decisions(actual)).hexdigest(),
                    "baseline":left,"current":right}

        for n in range(80):
            row = order(n)
            if n < 12:
                annotation(n, row)
        checks = {"cold": compare(), "unchanged": compare()}
        order(80)
        checks["one_order_appended"] = compare()
        assert checks["one_order_appended"]["current"]["batch_rows"] == [1]
        # A newly commissioned stream has a zero state tag. Its first ACK must
        # also appear on a warm workbench; ACME only accepts positive sts.
        assert not fresh.stream("cook/acks")
        ack = {"facility_id":fid,"zone_id":"cook","device_state":"damper_changed","command_id":"queue-test-command",
               "incident_id":"incident-order-000","ack_at":"2026-10-15T00:20:00+00:00","value":90}
        put("cook/acks", "first-ack", ack, core.identities["adapter"])
        checks["empty_stream_receives_first_ack"] = compare()
        acp = core.root + "/acp-food-a-inspection_notes"
        prior = admin.retrieve(acp)["body"]["m2m:acp"]
        admin.update(acp, {"m2m:acp":{"pv":{"acr":[{"acor":["CAdmin"],"acop":63}]}}})
        try:
            observe(fresh)
        except CSEError as exc:
            assert exc.rsc == 4103
            checks["private_notes_revoked_with_warm_cache"] = {"rsc":exc.rsc,"rqi":exc.result["rqi"],"queue_returned":False}
        else:
            raise AssertionError("The technician could still retrieve the queue after private stream access was revoked")
        admin.update(acp, {"m2m:acp":{"pv":prior["pv"]}})
        checks["permission_restored"] = compare()
        cmd_path = site["path"] + "/work_orders"
        before = admin.retrieve(cmd_path)["body"]["m2m:cnt"]
        admin.delete(cmd_path + "/order-009")
        after = admin.retrieve(cmd_path)["body"]["m2m:cnt"]
        assert before["st"] == after["st"] and before["cni"] - 1 == after["cni"]
        stale, _ = observe(old)
        assert any(o["work_order_id"] == "order-009" for o in stale["work_orders"])
        old.cache.clear()
        checks["delete_without_state_tag_increment"] = {**compare(),"previous_release_warm_showed_deleted_order":True,
                    "parent_tag_before_and_after":after["st"], "count_before":before["cni"], "count_after":after["cni"]}
        admin.update(cmd_path, {"m2m:cnt":{"mni":4}})
        order(81)
        old.cache.clear()
        checks["retention_rollover"] = compare()
        assert checks["retention_rollover"]["retained_orders"] == 4
        fresh.cache.clear()
        old.cache.clear()
        checks["cold_after_rollover"] = compare()
        observation, _ = observe(fresh)
        assert all(int(o["work_order_id"].split("-")[-1]) >= 78 for o in observation["work_orders"])
        return {"status":"passed","acme_version":version,"captured_at":datetime.now(timezone.utc).isoformat(),
                "scope":"Isolated real local ACME and the commissioned technician AE. Synthetic order/inspection history created through facility-scoped oneM2M roles. Elapsed times are one local run per case. No physical equipment or cloud MEC in this study.",
                "reference":"Baseline stream reader uses the 91a359e container read, discovery and individual CIN reads. Semantic comparisons exclude only native read-request IDs, which differ on each request. Native CSE resource IDs and all business fields remain in the digest.",
                "page_size":fresh.PAGE_SIZE,"checks":checks,
                "sha256":{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                           ("src/opensoom/technician.py","src/opensoom/maintenance.py","src/opensoom/onem2m.py",
                            "scripts/technician_queue_acceptance.py")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with ExitStack() as stack:
        folder = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-queue-")))
        processes = []
        stack.callback(lambda: [stop_process(p) for p in processes])
        url, _, version = start_cse(folder, processes)
        receipt = run(folder, url, version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({key:[v["baseline"]["calls"],v["current"]["calls"]] for key,v in receipt["checks"].items() if "current" in v}))

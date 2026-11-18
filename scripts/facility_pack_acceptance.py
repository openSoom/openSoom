"""Exercise a manager-defined virtual installation through the shipped stdio MCP plugin."""
import argparse
import asyncio
import json
from pathlib import Path

from mcp import Client
from opensoom.llm_runner import mcp_parameters, tool_result
from opensoom.mcp_server import ServiceProxy


ROOT = Path(__file__).resolve().parents[1]
PACK = {
    "site_id": "archive-workshop", "name": "Archive conservation workshop",
    "template": "learning-space", "adapter": "vendor-b",
    "zones": [
        {"id": "intake", "name": "Receiving", "minimum_airflow": 410, "pm25_warning": 22, "co2_warning": 920},
        {"id": "conservation", "name": "Conservation bench", "minimum_airflow": 560, "pm25_warning": 18, "co2_warning": 870},
    ],
    "maintenance": {"assets": {"conservation": {"asset_id": "bench-extract", "sensor_id": "bench-shaft"}},
                    "settle_seconds": 4, "freshness_seconds": 45, "tolerance_pct": 9},
}


async def call(client, name, fields, expected_error=None):
    result = await client.call_tool(name, fields)
    data = tool_result(result)["result"]
    if expected_error:
        if not result.is_error or expected_error not in str(data):
            raise RuntimeError(f"Expected {expected_error} for {name}: {data}")
        return expected_error
    if result.is_error:
        raise RuntimeError(f"{name}: {data}")
    return data


async def run(args):
    credentials = json.loads((args.runtime / "service-credentials.json").read_text())
    def connect(role):
        proxy = ServiceProxy(base_url=args.service, token=credentials[role + "_token"])
        return Client(mcp_parameters(ROOT, proxy), read_timeout_seconds=45)
    fid = PACK["site_id"]
    async with connect("operator") as operator:
        if args.phase == "install":
            refusal = await call(operator, "draft_facility", {**PACK, "zones": [PACK["zones"][0]]}, "invalid_facility")
            draft = await call(operator, "draft_facility", PACK)
            version = {"version": draft["version"]}
            denied = await call(operator, "activate_facility", version, "admin_required")
            async with connect("admin") as admin:
                active = await call(admin, "activate_facility", version)
                retry = await call(admin, "activate_facility", version)
            assert active["cse_path"] == retry["cse_path"] and active["zone_ids"] == ["intake", "conservation"]
            trial = await call(operator, "test_virtual_scenario", {
                "facility_id": fid, "zone_id": "conservation", "scenario_id": "bench-check",
                "observation_age_seconds": 92, "airflow_m3_h": 515,
                "damper_percent": 80, "expected_result": "command_refused", "request_id": "bench-first",
            })
            assert trial["assertion_passed"] and trial["asset_id"] == "bench-extract"
            report = {"scope": "Synthetic commissioning values; real plugin stdio and real oneM2M MN-CSE. Scripted operator and administrator, no hosted inference for this test.",
                      "draft": draft, "mapping_outside_zone_refused": refusal, "operator_activation": denied,
                      "admin_activation": active, "repeat_activation": retry, "original": trial}
        else:
            report = json.loads(args.output.read_text())
            discovery = await call(operator, "discover", {"facility_id": fid})
            site = next(x for x in discovery["facilities"] if x["id"] == fid)
            assert site["zones"][1]["id"] == "conservation"
            original = report["original"]
            old = await call(operator, "read_scenario_run", {"facility_id": fid, "execution_id": original["execution_id"]})
            replay = await call(operator, "run_scenario", {"facility_id": fid, "scenario_id": original["scenario_id"],
                                                           "version": original["version"], "request_id": "bench-second"})
            reread = await call(operator, "read_scenario_run", {"facility_id": fid, "execution_id": replay["execution_id"]})
            for trial in (old, reread):
                assert trial["assertion_passed"] and trial["actual_result"] == "command_refused"
                assert trial["command_state_tag_delta"] == 0 and trial["readback"]["airflow_m3_h"] == 515
                assert trial["zone_id"] == "conservation" and trial["asset_id"] == "bench-extract"
            assert old["readback"]["cin"] == original["readback"]["cin"] != reread["readback"]["cin"]
            report.update({"result": "passed", "after_service_restart": {"facility": site, "discovery": discovery["cse_discovery"],
                           "original": old, "replayed": reread}})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"phase": args.phase, "result": "passed", "site": fid, "version": report["draft"]["version"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("install", "after-restart"))
    parser.add_argument("--service", required=True)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    asyncio.run(run(parser.parse_args()))

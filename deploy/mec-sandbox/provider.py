"""Commission a simulated, independently operated shaft transducer on a private CSE."""
import argparse
from datetime import datetime, timezone
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def request(url, origin, method="GET", payload=None, ty=None):
    ri = "os-provider-" + uuid4().hex[:14]
    headers = {"X-M2M-Origin":origin, "X-M2M-RI":ri, "X-M2M-RVI":"4",
               "Content-Type":"application/json" + (f";ty={ty}" if ty else "")}
    req = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                  headers=headers, method=method)
    try:
        with urlopen(req, timeout=8) as res:
            return json.load(res)
    except HTTPError as error:
        raise RuntimeError(f"{method} {url.rsplit('/', 1)[-1]}: HTTP {error.code} RSC "
                           f"{error.headers.get('X-M2M-RSC')} {error.read().decode()[:270]}") from error


def ensure(url, parent, rn, key, ty, definition, origin):
    try:
        return request(f"{url}/{parent}{rn}", origin)[key]
    except RuntimeError as err:
        if "HTTP 404 " not in str(err):
            raise
    return request(f"{url}/{parent}".rstrip("/"), origin, "POST", {key:dict(rn=rn, **definition)}, ty)[key]


def send_sample(url, cycles):
    owner = "CProviderOwner"
    ae = ensure(url, "", "transducer", "m2m:ae", 2,
                {"api":"Norg.opensoom.transducer","rr":False,"srv":["4"]}, "COpenSoomTransducer")
    actor = ae["aei"]
    read_right = {"acor":["CAdmin"],"acop":34}
    manage = {"acor":[actor,owner],"acop":63}
    acl = ensure(url, "transducer/", "sensor-read", "m2m:acp", 1,
                 {"pv":{"acr":[manage,read_right]},"pvs":{"acr":[manage]}}, actor)
    for i in range(cycles):
        data = {"observed_at":datetime.now(timezone.utc).isoformat(),"facility_id":"food-a","zone_id":"cook",
                "asset_id":"extract-damper-01","sensor_id":"shaft-position-01","unit":"%","value":35,
                "source":"independent_position_sensor","simulated":True}
        sample = json.dumps(data, separators=(",", ":"))
        sensor = ensure(url, "transducer/", "shaft", "os:shaft", 28,
                        {"cnd":"org.opensoom.provider.shaftPosition.v1","sample":sample,"acpi":[acl["ri"]]}, actor)
        sensor = request(f"{url}/transducer/shaft", actor, "PUT", {"os:shaft":{"sample":sample}})["os:shaft"]
        print(json.dumps({"sensor_ri":sensor["ri"],"state_tag":sensor["st"],"source_observed_at":data["observed_at"]}),flush=True)
        if i < cycles - 1:
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cse")
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args()
    send_sample(args.cse.rstrip("/"), args.cycles)

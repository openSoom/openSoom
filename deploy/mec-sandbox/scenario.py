"""Build two ETSI topology scenarios. Both eligible logical edges share the one test VM."""
from argparse import ArgumentParser
import json
from uuid import NAMESPACE_DNS, uuid5


NET = {"latency":1,"latencyVariation":0,"throughputDl":100,"throughputUl":100,"packetLoss":0}

def node(name, kind, **extra):
    return {"id":str(uuid5(NAMESPACE_DNS,"opensoom.test/"+name)),"name":name,"type":kind,"netChar":dict(NET),**extra}


def scenario(selected):
    chosen=selected+"-edge"
    child=node("inspection-worker","EDGE-APP",userChartLocation="maintenance",
               userChartAlternateValues=f"maintenance/{selected}.yaml")
    mn=node("site-mn-cse","EDGE-APP",userChartLocation="site-mn",
            userChartAlternateValues=f"site-mn/{selected}.yaml")
    zones=[]
    for side in ["north","south"]:
        name=side+"-edge"
        host=node(name,"EDGE",connected=True, processes=[child,mn] if name==chosen else [])
        location=node(side+"-DEFAULT","DEFAULT",physicalLocations=[host])
        zones.append(node(side,"ZONE",networkLocations=[location]))
    return {"version":"1.8.1","name":"inspection-"+selected,
            "description":"Simulated facility topology with two alternative locations for the same read-and-ticket app.",
            "deployment":{"netChar":dict(NET),"connectivity":{"model":"OPEN"},"domains":[node("facility-provider","OPERATOR",zones=zones)]}}


if __name__=="__main__":
    p=ArgumentParser()
    p.add_argument("selected",choices=["north","south"])
    print(json.dumps(scenario(p.parse_args().selected)))

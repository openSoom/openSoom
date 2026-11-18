"""Inspect or remove the installed bridge's owned MEC 046 subscription."""
import argparse
import json
import os

from opensoom.mec_sensor import SensorService


def inspect_slot(operation):
    config = json.loads(os.environ["OPENSOOM_WORKER_CONFIG_JSON"])
    service = SensorService(config, os.environ.get("OPENSOOM_MEC_TOKEN"))
    try:
        return service.data_subscription(remove=operation == "remove")
    finally:
        service.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["read", "remove"])
    print(json.dumps(inspect_slot(parser.parse_args().action), indent=2))

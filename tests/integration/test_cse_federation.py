"""Intent boundary failures; live multi-CSE execution has its own smoke script."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from opensoom.core import OperationError
from opensoom.federation import FederationReceiver
from opensoom.store import Store


class LocalCore:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = Store(runtime / "test.sqlite")
        self.profiles = {"food-production": {"command_ttl_seconds": 30}}
        self.calls = []

    def facility(self, fid):
        return {"id": fid, "profile": "food-production", "profile_version": 1}

    def request_action(self, request, principal):
        self.calls.append((request, principal))
        command = {"id": "cmd-" + str(len(self.calls)), **request.model_dump()}
        self.store.put("commands", command["id"], command)
        return command

    def log(self, *args, **kwargs):
        pass


class FederationBoundaryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.core = LocalCore(Path(directory.name))
        self.receiver = FederationReceiver(self.core, "food-a", "food-production", "queue-resource")

    def result(self, **changes):
        issued = datetime.now(timezone.utc) - timedelta(seconds=1)
        intent = {"schema_version": 1, "request_id": "central-test", "facility_id": "food-a", "zone_id": "cook", "profile_id": "food-production", "profile_version": 1, "issued_at": issued.isoformat(), "expires_at": (issued + timedelta(seconds=20)).isoformat(), "action": "set_damper", "value": 100.0, "reason": "Virtual test", **changes}
        return {"rsc": 2000, "rqi": "retrieval-request", "body": {"m2m:cin": {"ty": 4, "ri": "intent-resource", "pi": "queue-resource", "con": json.dumps(intent)}}}

    def test_expired_or_wrong_scope_never_reaches_local_action(self):
        expired = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        cases = [({"issued_at": (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat(), "expires_at": expired}, "central_intent_expired"), ({"facility_id": "learning-b"}, "central_facility_mismatch"), ({"profile_version": 2}, "central_profile_mismatch")]
        for index, (changes, code) in enumerate(cases):
            with self.subTest(code=code):
                result = self.receiver.receive(self.result(request_id="case-" + str(index), **changes))
                self.assertEqual(result["code"], code)
                self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.core.calls, [])

    def test_replay_survives_a_new_receiver_without_duplicate_dispatch(self):
        source = self.result()
        accepted = self.receiver.receive(source)
        second = FederationReceiver(self.core, "food-a", "food-production", "queue-resource")
        replay = second.receive(source)
        self.assertTrue(replay["replayed"])
        self.assertEqual(accepted["command_id"], replay["command_id"])
        self.assertEqual(len(self.core.calls), 1)
        self.assertEqual(self.core.calls[0][1], {"role": "operator", "facilities": ["food-a"]})

    def test_reused_request_id_with_different_content_is_rejected(self):
        source = self.result()
        self.receiver.receive(source)
        body = json.loads(source["body"]["m2m:cin"]["con"])
        body["value"] = 80.0
        source["body"]["m2m:cin"]["con"] = json.dumps(body)
        with self.assertRaises(OperationError) as error:
            self.receiver.receive(source)
        self.assertEqual(error.exception.code, "central_idempotency_conflict")
        self.assertEqual(len(self.core.calls), 1)

    def test_payload_cannot_supply_privilege_and_wrong_queue_is_rejected(self):
        with self.assertRaises(OperationError) as error:
            self.receiver.receive(self.result(role="admin"))
        self.assertEqual(error.exception.code, "invalid_central_intent")
        source = self.result()
        source["body"]["m2m:cin"]["pi"] = "another-queue"
        with self.assertRaises(OperationError) as error:
            self.receiver.receive(source)
        self.assertEqual(error.exception.code, "intent_source_mismatch")
        self.assertEqual(self.core.calls, [])


if __name__ == "__main__":
    unittest.main()

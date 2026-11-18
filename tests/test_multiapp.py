"""Boundary tests for the independent CSE consumers; runtime proof is separate."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from opensoom.models import Observation
from opensoom.multiapp import Application, command_is_allowed, observation_from_event

ROOT = Path(__file__).resolve().parents[1]


class MultiApplicationBoundaries(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.profile = json.loads((ROOT / "profiles/food-production.json").read_text())
        self.config = {"event_id": "event-1", "facility_id": "food-a", "asset_id": "cook-exhaust-01",
                       "target_zone": "cook", "profile": self.profile,
                       "zones": {zone["id"]: zone for zone in self.profile["zones"]},
                       "simulation_only": True, "controls_enabled": True}
        self.command = {"event_id": "event-1", "facility_id": "food-a", "zone_id": "cook", "asset_id": "cook-exhaust-01",
                        "profile_id": "food-production", "profile_version": 1, "action": "set_damper", "value": 100,
                        "command_id": "command-1", "issued_at": (self.now - timedelta(seconds=1)).isoformat(),
                        "expires_at": (self.now + timedelta(seconds=2)).isoformat()}

    def observation(self, critical=False, **changes):
        return Observation(facility_id="food-a", zone_id="cook", adapter="vendor-a", observed_at=self.now.isoformat(),
                           airflow=300 if critical else 1100, pm25=60 if critical else 20, co2=700,
                           fan_running=True, damper_pct=100, **changes)

    def operations(self):
        app = Application.__new__(Application)
        app.config = self.config
        app.state = {"status": "awaiting_ack", "command": self.command, "command_creation": {"body": {"m2m:cin": {"ri": "command-ri"}}},
                     "recovery_samples": 0, "unresolved_samples": 0}
        app.transitions = []
        def transition(status, **details):
            app.state["status"] = status
            app.transitions.append({"status": status, **details})
        app.transition = transition
        app.save = lambda: None
        return app

    def ack(self, **changes):
        return {"event_id": "event-1", "command_id": "command-1", "command_ri": "command-ri", "simulated": True,
                "device_state": "damper_changed", "ack_at": (self.now - timedelta(milliseconds=500)).isoformat(), **changes}

    def test_virtual_adapter_rejects_scope_permission_profile_and_expiry(self):
        self.assertTrue(command_is_allowed(self.command, self.config, self.now))
        for changes in ({"event_id": "other"}, {"facility_id": "learning-b"}, {"zone_id": "wash"},
                        {"profile_version": 2}, {"action": "grant_permission"}, {"value": 80},
                        {"expires_at": (self.now - timedelta(milliseconds=1)).isoformat()},
                        {"expires_at": (self.now + timedelta(minutes=2)).isoformat()}, {"issued_at": "invalid"}):
            with self.subTest(changes=changes):
                self.assertFalse(command_is_allowed({**self.command, **changes}, self.config, self.now))
        for changes in ({"simulation_only": False}, {"controls_enabled": False}):
            self.assertFalse(command_is_allowed(self.command, {**self.config, **changes}, self.now))

    def test_observation_must_match_configured_event_asset_and_facility(self):
        event = {"schema_version": 1, "event_id": "event-1", "asset_id": "cook-exhaust-01", "observation": self.observation().model_dump()}
        self.assertEqual(observation_from_event(event, self.config).zone_id, "cook")
        for key, value in (("event_id", "different"), ("asset_id", "other"), ("schema_version", 2)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                observation_from_event({**event, key: value}, self.config)
        changed = deepcopy(event)
        changed["observation"]["facility_id"] = "learning-b"
        with self.assertRaises(ValueError):
            observation_from_event(changed, self.config)

    def test_ack_alone_and_uncorrelated_ack_cannot_establish_recovery(self):
        for changes in ({"command_id": "other"}, {"command_ri": "other-ri"}, {"event_id": "other"},
                        {"simulated": False}, {"ack_at": (self.now + timedelta(seconds=3)).isoformat()}):
            app = self.operations()
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                app.operations_ack(self.ack(**changes), {"rqi": "ack-read"})
            self.assertEqual(app.state["status"], "awaiting_ack")
        app = self.operations()
        app.operations_ack(self.ack(), {"rqi": "ack-read"})
        self.assertEqual(app.state["status"], "awaiting_outcome")
        self.assertNotEqual(app.state["status"], "verified_recovery")

    def test_recovery_requires_consecutive_fresh_samples_after_ack(self):
        app = self.operations()
        app.operations_ack(self.ack(), {"rqi": "ack-read"})
        result = {"body": {"m2m:cin": {"ri": "observation-ri"}}, "rqi": "observation-read"}
        app.operations_observation(self.observation(), result)
        self.assertEqual(app.state["status"], "awaiting_outcome")
        app.operations_observation(self.observation(critical=True), result)
        app.operations_observation(self.observation(), result)
        self.assertEqual(app.state["status"], "awaiting_outcome")
        app.operations_observation(self.observation(), result)
        self.assertEqual(app.state["status"], "verified_recovery")

    def test_stale_or_pre_ack_samples_do_not_verify_a_command(self):
        app = self.operations()
        app.operations_ack(self.ack(), {"rqi": "ack-read"})
        result = {"body": {"m2m:cin": {"ri": "observation-ri"}}, "rqi": "observation-read"}
        pre_ack = self.observation().model_copy(update={"observed_at": (self.now - timedelta(seconds=1)).isoformat()})
        app.operations_observation(pre_ack, result)
        self.assertEqual(app.state["recovery_samples"], 0)
        stale = self.observation().model_copy(update={"observed_at": (self.now - timedelta(minutes=2)).isoformat()})
        app.operations_observation(stale, result)
        self.assertEqual(app.state["status"], "awaiting_outcome")

    def test_invalid_sample_breaks_both_outcome_streaks(self):
        invalid_samples = [
            self.observation().model_copy(update={"observed_at": (self.now - timedelta(minutes=2)).isoformat()}),
            self.observation().model_copy(update={"airflow": None}),
        ]
        for critical in (False, True):
            for invalid in invalid_samples:
                with self.subTest(critical=critical, invalid=invalid):
                    app = self.operations()
                    app.operations_ack(self.ack(), {"rqi": "ack-read"})
                    for obs in (self.observation(critical), invalid, self.observation(critical)):
                        app.operations_observation(obs, {"rqi": "sample-read"})
                    self.assertEqual(app.state["status"], "awaiting_outcome")
                    app.operations_observation(self.observation(critical), {"rqi": "next-read"})
                    expected = "unresolved_after_ack" if critical else "verified_recovery"
                    self.assertEqual(app.state["status"], expected)

    def test_samples_delivered_before_ack_notification_are_correlated_after_ack(self):
        app = self.operations()
        for sequence in (1, 2):
            event = {"schema_version": 1, "event_id": "event-1", "asset_id": "cook-exhaust-01",
                     "sequence": sequence, "observation": self.observation().model_dump()}
            result = {"body": {"m2m:cin": {"ri": f"sample-{sequence}", "con": json.dumps(event)}}, "rqi": f"read-{sequence}"}
            app.operations_observation(self.observation(), result)
        self.assertEqual(app.state["status"], "awaiting_ack")
        app.operations_ack(self.ack(), {"rqi": "ack-read"})
        self.assertEqual(app.state["status"], "verified_recovery")


if __name__ == "__main__":
    unittest.main()

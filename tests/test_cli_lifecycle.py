import json
import os
import sys
from types import SimpleNamespace

import pytest

from opensoom import cli


@pytest.fixture(autouse=True)
def isolated_runtime_environment():
    previous = {key: os.environ[key] for key in cli.RUNTIME_KEYS if key in os.environ}
    for key in cli.RUNTIME_KEYS:
        os.environ.pop(key, None)
    yield
    for key in cli.RUNTIME_KEYS:
        os.environ.pop(key, None)
    os.environ.update(previous)


def test_saved_secure_configuration_and_port_survive_without_environment(tmp_path):
    saved = cli.resolve_config(tmp_path, {}, {"OPENAI_API_KEY": "never-persist", "OPENSOOM_SERVICE_TOKEN": "never-persist"}, 8179, True)
    restarted = cli.resolve_config(tmp_path, saved, {}, None, False)
    assert restarted == saved
    assert restarted["environment"]["OPENSOOM_CSE_URL"].startswith("https://")
    assert restarted["environment"]["OPENSOOM_MQTT_PORT"] == "8883"
    assert "never-persist" not in json.dumps(saved)
    assert restarted["port"] == 8179


def test_legacy_stop_migrates_settings_before_removing_pid(tmp_path, monkeypatch, capsys):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    (runtime / "service-process.json").write_text(json.dumps({"pid": 123, "port": 8179, "environment": {"OPENSOOM_CSE_URL": "https://127.0.0.1:8643", "OPENSOOM_CSE_BASE": "cse-secure", "API_KEY": "never-persist"}}))
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "process_info", lambda pid, root: (False, False))
    monkeypatch.setattr(sys, "argv", ["opensoom", "stop"])
    cli.main()
    assert not (runtime / "service-process.json").exists()
    saved = json.loads((runtime / "service-config.json").read_text())
    assert saved["port"] == 8179
    assert saved["environment"]["OPENSOOM_CSE_BASE"] == "cse-secure"
    assert "API_KEY" not in saved["environment"]


def test_stop_timeout_retains_record(tmp_path, monkeypatch):
    pidfile = tmp_path / "service-process.json"
    pidfile.write_text('{"pid":123}')
    monkeypatch.setattr(cli, "process_info", lambda pid, root: (True, True))
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    with pytest.raises(RuntimeError, match="did not stop"):
        cli.stop_service(pidfile, tmp_path, timeout=0)
    assert pidfile.exists() and len(signals) == 1


def test_unrelated_process_is_never_signalled(tmp_path, monkeypatch):
    pidfile = tmp_path / "service-process.json"
    pidfile.write_text('{"pid":123}')
    monkeypatch.setattr(cli, "process_info", lambda pid, root: (True, False))
    monkeypatch.setattr(cli.os, "kill", lambda *_: pytest.fail("Unrelated PID was signalled"))
    with pytest.raises(RuntimeError, match="refusing"):
        cli.stop_service(pidfile, tmp_path)
    assert pidfile.exists()


def test_stop_waits_through_cwd_disappearing_during_exit(tmp_path, monkeypatch):
    pidfile = tmp_path / "service-process.json"
    pidfile.write_text('{"pid":123}')
    states = iter([(True, True), (True, False), (False, False)])
    monkeypatch.setattr(cli, "process_info", lambda pid, root: next(states))
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    cli.stop_service(pidfile, tmp_path)
    assert len(signals) == 1 and not pidfile.exists()


def test_cleanup_preserves_configuration_and_shared_budget(tmp_path, monkeypatch):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    config = cli.resolve_config(tmp_path, {}, {}, 8179, True)
    cli.write_json(runtime / "service-config.json", config)
    (runtime / "llm-budget.sqlite").write_bytes(b"durable-budget")
    (runtime / "operations.sqlite").write_bytes(b"disposable-state")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["opensoom", "cleanup"])
    cli.main()
    assert not (runtime / "operations.sqlite").exists()
    assert (runtime / "llm-budget.sqlite").read_bytes() == b"durable-budget"
    assert json.loads((runtime / "service-config.json").read_text()) == config


def test_doctor_applies_saved_runtime_configuration(tmp_path, monkeypatch, capsys):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    config = cli.resolve_config(tmp_path, {}, {}, 8179, True)
    cli.write_json(runtime / "service-config.json", config)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    for key in cli.RUNTIME_KEYS:
        monkeypatch.delenv(key, raising=False)
    class DiagnosticCore:
        cse = type("Connection", (), {"close": lambda _: None})()
        def __init__(self):
            assert cli.os.environ["OPENSOOM_CSE_BASE"] == "cse-secure"
            assert cli.os.environ["OPENSOOM_CSE_URL"].startswith("https://")
        def doctor(self):
            return {"status": "ready", "cse": {"connected": True}}
    monkeypatch.setattr(cli, "Core", DiagnosticCore)
    monkeypatch.setattr(sys, "argv", ["opensoom", "doctor"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1  # CSE alone is insufficient when the service is stopped.
    assert json.loads(capsys.readouterr().out)["service"]["port"] == 8179


def test_foreground_serve_uses_saved_settings_and_cleans_its_own_record(tmp_path, monkeypatch):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    config = cli.resolve_config(tmp_path, {}, {}, 8179, True)
    cli.write_json(runtime / "service-config.json", config)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    def serve(application, **kwargs):
        assert kwargs["port"] == 8179
        assert json.loads((runtime / "service-process.json").read_text())["pid"] == os.getpid()
        assert os.environ["OPENSOOM_CSE_BASE"] == "cse-secure"
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=serve))
    monkeypatch.setattr(sys, "argv", ["opensoom", "serve"])
    cli.main()
    assert not (runtime / "service-process.json").exists()
    assert json.loads((runtime / "service-config.json").read_text()) == config

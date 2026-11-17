import httpx
import pytest

from opensoom.llm_budget import BudgetLimits, SharedBudget
from opensoom.llm_runner import ProviderFailure, ResponsesProvider, provider_settings, verify_trace


def test_ack_or_status_alone_cannot_pass_recovery():
    calls = [
        {"name": "read_evidence", "output": {"is_error": False, "result": {}}},
        {"name": "request_action", "output": {"is_error": False, "result": {"id": "command"}}},
        {"name": "verify_result", "output": {"is_error": False, "result": {"command_id": "command", "status": "verified", "ack": True, "complete": False, "observed_result": "unresolved"}}},
    ]
    assert verify_trace(calls, "recovered")[0] is False
    calls[-1]["output"]["result"].update(complete=True, observed_result="recovered")
    assert verify_trace(calls, "recovered")[0] is True
    assert verify_trace(calls, "unresolved")[0] is False


def test_historical_verified_command_cannot_pass_a_new_run():
    calls = [
        {"name": "read_evidence", "output": {"is_error": False, "result": {"status": "critical"}}},
        {"name": "request_action", "output": {"is_error": False, "result": {"id": "old-command", "run_id": "previous"}}},
        {"name": "verify_result", "output": {"is_error": False, "result": {
            "command_id": "old-command", "run_id": "previous", "complete": True, "ack": True, "observed_result": "recovered"}}},
    ]
    assert verify_trace(calls, "recovered", "current")[0] is False
    calls[1]["output"]["result"]["run_id"] = "current"
    calls[2]["output"]["result"]["run_id"] = "current"
    assert verify_trace(calls, "recovered", "current")[0] is True


def test_denial_remains_a_failure_outcome():
    calls = [
        {"name": "read_evidence", "output": {"is_error": False, "result": {"zones": []}}},
        {"name": "request_action", "output": {"is_error": True, "result": {"code": "action_denied"}}},
    ]
    assert verify_trace(calls, "unresolved")[0] is True
    assert verify_trace(calls, "recovered")[0] is False


def test_pending_or_unrelated_error_is_not_confirmed_failure():
    calls = [
        {"name": "read_evidence", "output": {"is_error": False, "result": {"status": "critical", "zones": []}}},
        {"name": "verify_result", "output": {"is_error": False, "result": {
            "status": "requested", "ack": False, "observed_result": "pending", "outcome": "unresolved"}}},
    ]
    assert verify_trace(calls, "unresolved")[0] is False
    calls.append({"name": "doctor", "output": {"is_error": True, "result": {"code": "SERVICE_UNAVAILABLE"}}})
    assert verify_trace(calls, "unresolved")[0] is False


def test_freshness_refusal_and_later_unresolved_observations_are_valid_negative_evidence():
    stale = [{"name": "read_evidence", "output": {"is_error": False, "result": {"status": "stale"}}}]
    assert verify_trace(stale, "unresolved")[0] is True
    stale[0]["output"]["result"] = {"status": "critical", "note": "The previous run was stale"}
    assert verify_trace(stale, "unresolved")[0] is False
    stale.append({"name": "verify_result", "output": {"is_error": False, "result": {
        "status": "unresolved", "observed_result": "unresolved", "ack": True}}})
    assert verify_trace(stale, "unresolved")[0] is True


def test_provider_error_never_turns_into_a_fixture_pass(tmp_path):
    budget = SharedBudget(tmp_path / "budget.sqlite", BudgetLimits("test", 3, 50000))
    provider = ResponsesProvider("https://example.test/v1", "secret", budget,
                                 {"max_attempts_per_step": 1, "max_output_tokens_per_response": 4096, "timeout_seconds": 1},
                                 transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": "secret"}})))
    with pytest.raises(ProviderFailure) as caught:
        provider.generate({"model": "example", "input": "test"}, "run", 0)
    assert "secret" not in str(caught.value)
    assert budget.snapshot()["requests_consumed"] == 1
    assert budget.snapshot()["tokens_charged"] > 0


def test_retry_consumes_a_separate_shared_reservation(tmp_path, monkeypatch):
    monkeypatch.setattr("opensoom.llm_runner.time.sleep", lambda _: None)
    calls = []
    def response(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"code": "rate_limit"}})
        return httpx.Response(200, json={"output": [], "usage": {"total_tokens": 12}})
    budget = SharedBudget(tmp_path / "budget.sqlite", BudgetLimits("test", 3, 50000))
    provider = ResponsesProvider("https://example.test/v1", "secret", budget,
                                 {"max_attempts_per_step": 2, "max_output_tokens_per_response": 4096, "timeout_seconds": 1},
                                 transport=httpx.MockTransport(response))
    assert provider.generate({"model": "example", "input": "test"}, "run", 0)["usage"]["total_tokens"] == 12
    assert len(calls) == budget.snapshot()["requests_consumed"] == 2
    assert budget.snapshot()["tokens_charged"] > 12


def test_custom_provider_never_receives_openai_key_implicitly(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-send-to-local")
    monkeypatch.setenv("OPENSOOM_LLM_BASE_URL", "http://127.0.0.1:10000/v1")
    monkeypatch.delenv("OPENSOOM_LLM_API_KEY", raising=False)
    _, key, kind = provider_settings()
    assert key == "" and kind == "local"

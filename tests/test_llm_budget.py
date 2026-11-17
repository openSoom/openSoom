from concurrent.futures import ThreadPoolExecutor

import pytest

from opensoom.llm_budget import BudgetConfigurationError, BudgetExhausted, BudgetLimits, SharedBudget


def test_workers_cannot_over_reserve_and_restart_preserves_usage(tmp_path):
    path = tmp_path / "budget.sqlite"
    SharedBudget(path, BudgetLimits("shared", 3, 90))

    def worker(i):
        try:
            SharedBudget(path).reserve(str(i), "run-" + str(i), 30)
            return True
        except BudgetExhausted:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(worker, range(12))) == 3
    restarted = SharedBudget(path)
    assert restarted.snapshot()["requests_consumed"] == 3
    assert restarted.snapshot()["tokens_charged"] == 90
    with pytest.raises(BudgetExhausted):
        restarted.reserve("later", "resumed", 1)


def test_unknown_failed_request_stays_charged(tmp_path):
    budget = SharedBudget(tmp_path / "b.sqlite", BudgetLimits("batch", 5, 100))
    budget.reserve("first", "run", 80)
    budget.settle("first", None)
    assert budget.snapshot()["tokens_charged"] == 80
    assert budget.snapshot()["pending_requests"] == 0
    with pytest.raises(BudgetExhausted):
        budget.reserve("retry", "run", 30)


def test_known_usage_releases_only_unused_reservation(tmp_path):
    budget = SharedBudget(tmp_path / "b.sqlite", BudgetLimits("batch", 5, 100))
    budget.reserve("first", "run", 80)
    budget.settle("first", 25)
    assert budget.snapshot()["tokens_charged"] == 25
    with pytest.raises(BudgetConfigurationError):
        budget.settle("first", 0)
    with pytest.raises(BudgetConfigurationError):
        budget.reserve("first", "run", 20)


def test_reopening_does_not_raise_limits_or_reset(tmp_path):
    path = tmp_path / "b.sqlite"
    budget = SharedBudget(path, BudgetLimits("batch", 5, 100))
    budget.reserve("first", "run", 50)
    with pytest.raises(BudgetConfigurationError):
        SharedBudget(path, BudgetLimits("batch", 50, 1000))
    assert SharedBudget(path).snapshot()["tokens_charged"] == 50


def test_unexpected_usage_blocks_later_calls_and_survives_reopen(tmp_path):
    path = tmp_path / "b.sqlite"
    budget = SharedBudget(path, BudgetLimits("batch", 5, 100))
    budget.reserve("first", "run", 20)
    with pytest.raises(BudgetConfigurationError):
        budget.settle("first", 25)
    assert SharedBudget(path).snapshot()["requires_investigation"] is True
    with pytest.raises(BudgetConfigurationError):
        SharedBudget(path).reserve("later", "run", 1)

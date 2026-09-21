from concurrent.futures import ThreadPoolExecutor

import pytest

from deep_research.models.spend import SpendLedger, SpendLimitError


def test_reservations_survive_restart_and_settlement_releases_capacity(tmp_path):
    path = tmp_path / "spend.sqlite"
    ledger = SpendLedger(path, 0.01)
    call = ledger.reserve("gpt-4.1", 1000, 1000)
    restarted = SpendLedger(path, 0.01)
    with pytest.raises(SpendLimitError):
        restarted.reserve("gpt-4.1", 1, 1)
    restarted.settle(call, 100, 100)
    assert restarted.summary()["estimated_cost_usd"] == pytest.approx(0.001)
    assert restarted.summary()["reserved_usd"] == 0
    restarted.reserve("gpt-4.1-mini", 100, 100)
    assert restarted.summary([call])["calls"] == 1


def test_parallel_workers_cannot_overbook_budget(tmp_path):
    path = tmp_path / "spend.sqlite"
    ledgers = [SpendLedger(path, 0.01) for _ in range(8)]

    def reserve(ledger):
        try:
            ledger.reserve("gpt-4.1", 1000, 1000)
            return True
        except SpendLimitError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reserve, ledgers)) == 1
    assert ledgers[0].summary()["reserved_usd"] == pytest.approx(0.01)


def test_unknown_model_fails_before_reservation(tmp_path):
    ledger = SpendLedger(tmp_path / "spend.sqlite", 17)
    with pytest.raises(SpendLimitError, match="No verified token price"):
        ledger.reserve("unknown-model", 100, 100)
    assert ledger.summary()["calls"] == 0

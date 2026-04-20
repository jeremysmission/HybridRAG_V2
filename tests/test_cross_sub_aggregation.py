"""Adversarial and functional tests for CrossSubstrateExecutor."""

from __future__ import annotations

import pytest
from pathlib import Path

from src.query.aggregation_executor import CrossSubstrateExecutor


@pytest.fixture
def executor():
    return CrossSubstrateExecutor(data_dir="data")


@pytest.mark.parametrize("query,expected_tier,reason", [
    ("cost per failure for top parts in GOTHAM", "RED", "unknown system"),
    ("cost per failure for top parts at Antarctica", "RED", "unknown site"),
    ("cost per failure for top parts; DROP TABLE failure_events; --", "RED", "adversarial SQL"),
    ("cost per failure; DELETE FROM po_pricing; --", "RED", "adversarial SQL"),
    ("top vendors by spend; UNION SELECT * FROM sqlite_master; --", "RED", "adversarial SQL"),
])
def test_adversarial_tier_down(executor, query, expected_tier, reason):
    result = executor.try_execute(query)
    assert result is not None, f"Expected RED for {reason}, got None (passthrough)"
    assert result.tier == expected_tier, f"Expected {expected_tier} for {reason}, got {result.tier}"


def test_sql_injection_does_not_modify_substrate(executor):
    if not executor._failure_conn:
        pytest.skip("no failure_events substrate")
    before = executor._failure_conn.execute("SELECT COUNT(*) FROM failure_events").fetchone()[0]
    result = executor.try_execute("cost per failure; DROP TABLE failure_events; --")
    assert result is not None
    assert result.tier == "RED"
    after = executor._failure_conn.execute("SELECT COUNT(*) FROM failure_events").fetchone()[0]
    assert before == after, f"Substrate modified: {before} -> {after}"


def test_clean_query_returns_green(executor):
    if not executor._po_pricing_conn or not executor._failure_conn:
        pytest.skip("substrates not available")
    result = executor.try_execute("cost per failure for top parts")
    assert result is not None
    assert result.tier == "GREEN"
    assert len(result.ranked_rows) > 0


def test_top_vendors_returns_green(executor):
    if not executor._po_pricing_conn:
        pytest.skip("po_pricing not available")
    result = executor.try_execute("top vendors by spend")
    assert result is not None
    assert result.tier == "GREEN"
    assert len(result.ranked_rows) > 0

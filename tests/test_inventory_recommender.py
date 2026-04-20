from __future__ import annotations
import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.query.aggregation_executor import (
    AggregationExecutor,
    AliasTables,
    detect_inventory_intent,
)
from src.store.failure_events_store import FailureEvent, FailureEventsStore


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = (year * 12 + (month - 1)) + delta
    return absolute // 12, absolute % 12 + 1


def _seed_monthly_events(
    store: FailureEventsStore,
    *,
    part_number: str,
    system: str,
    site_token: str,
    start_year: int,
    start_month: int,
    months: int,
    counts_by_offset: dict[int, int] | None = None,
) -> None:
    events: list[FailureEvent] = []
    counts_by_offset = counts_by_offset or {}
    for offset in range(months):
        year, month = _add_months(start_year, start_month, offset)
        count = counts_by_offset.get(offset, 1)
        for idx in range(count):
            events.append(
                FailureEvent(
                    source_path=f"{part_number}_{site_token}_{year}_{month:02d}_{idx}.pdf",
                    chunk_id=f"{part_number}-{site_token}-{offset}-{idx}",
                    part_number=part_number,
                    system=system,
                    site_token=site_token,
                    event_year=year,
                    event_date=f"{year}-{month:02d}-15",
                    incident_id=f"INC-{part_number}-{offset:02d}-{idx}",
                    extraction_method="seed",
                    confidence=0.95,
                )
            )
    store.insert_many(events)


@pytest.fixture
def inventory_store(tmp_path):
    db = tmp_path / "failure_events.sqlite3"
    store = FailureEventsStore(db)
    _seed_monthly_events(
        store,
        part_number="ARC-4471",
        system="NEXION",
        site_token="djibouti",
        start_year=2023,
        start_month=1,
        months=24,
    )
    _seed_monthly_events(
        store,
        part_number="WR-200",
        system="NEXION",
        site_token="guam",
        start_year=2023,
        start_month=7,
        months=18,
    )
    _seed_monthly_events(
        store,
        part_number="AB-115",
        system="NEXION",
        site_token="thule",
        start_year=2024,
        start_month=5,
        months=8,
    )
    _seed_monthly_events(
        store,
        part_number="FM-440",
        system="NEXION",
        site_token="guam",
        start_year=2024,
        start_month=1,
        months=3,
        counts_by_offset={1: 0},
    )
    yield store
    store.close()


@pytest.fixture
def inventory_executor(inventory_store):
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    return AggregationExecutor(inventory_store, aliases)


def test_detect_inventory_intent_reorder_point():
    assert detect_inventory_intent(
        "What should our reorder point be for ARC-4471 at Djibouti in NEXION?"
    )


def test_detect_inventory_intent_stock_phrase():
    assert detect_inventory_intent("What should we stock for WR-200 in Guam?")


def test_detect_inventory_intent_inventory_for_phrase():
    assert detect_inventory_intent("Inventory for AB-115 at Thule")


def test_detect_inventory_intent_negative_for_failure_aggregation():
    assert not detect_inventory_intent("Top 5 failing parts in NEXION in 2024")


def test_monthly_history_zero_fills_missing_months(inventory_store):
    history = inventory_store.monthly_failure_history(
        "FM-440", system="NEXION", site_token="guam", trailing_months=24
    )
    assert history["span_months"] == 3
    assert history["month_counts"] == [1, 0, 1]


def test_recommend_reorder_point_green_history(inventory_executor):
    result = inventory_executor.recommend_reorder_point(
        "ARC-4471", "djibouti", "NEXION"
    )
    assert result.tier == "GREEN"
    assert result.parsed_params["history_months"] == 24
    assert result.ranked_rows[0]["recommended_units"] == 3


def test_recommend_reorder_point_green_formula_values(inventory_executor):
    result = inventory_executor.recommend_reorder_point(
        "ARC-4471", "djibouti", "NEXION"
    )
    row = result.ranked_rows[0]
    assert row["lead_time_days"] == 90
    assert row["monthly_sigma"] == pytest.approx(0.0)
    assert row["daily_demand_rate"] == pytest.approx(12 / 365, rel=1e-6)
    assert row["reorder_point"] == pytest.approx((12 / 365) * 90, rel=1e-6)


def test_recommend_reorder_point_yellow_history(inventory_executor):
    result = inventory_executor.recommend_reorder_point(
        "WR-200", "guam", "NEXION"
    )
    assert result.tier == "YELLOW"
    assert result.parsed_params["history_months"] == 18
    assert "provisional" in result.message


def test_recommend_reorder_point_red_insufficient_history(inventory_executor):
    result = inventory_executor.recommend_reorder_point(
        "AB-115", "thule", "NEXION"
    )
    assert result.tier == "RED"
    assert "at least 12 months" in result.message


def test_try_execute_inventory_query_green(inventory_executor):
    result = inventory_executor.try_execute(
        "What should our reorder point be for ARC-4471 at Djibouti in NEXION?"
    )
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["query_mode"] == "INVENTORY"
    assert "recommended reorder point" in result.context_text.lower()


def test_try_execute_inventory_query_missing_part_returns_red(inventory_executor):
    result = inventory_executor.try_execute(
        "What should our reorder point be at Djibouti in NEXION?"
    )
    assert result is not None
    assert result.tier == "RED"
    assert "explicit part number" in result.message


def test_try_execute_inventory_query_unknown_site_returns_red(inventory_executor):
    result = inventory_executor.try_execute(
        "What should our reorder point be for ARC-4471 at Atlantis in NEXION?"
    )
    assert result is not None
    assert result.tier == "RED"
    assert "unknown site" in result.message


def test_try_execute_inventory_query_without_system_uses_any_system(inventory_executor):
    result = inventory_executor.try_execute(
        "What should we stock for ARC-4471 at Djibouti?"
    )
    assert result is not None
    assert result.tier == "GREEN"
    assert result.ranked_rows[0]["part_number"] == "ARC-4471"


@pytest.mark.parametrize(
    ("query", "reason_snippet"),
    [
        (
            "What should our reorder point be for ARC-4471 at Djibouti in NEXION; DROP TABLE failure_events; --?",
            "hostile inventory input blocked",
        ),
        (
            "What should our reorder point be for ZX-9999 at Djibouti in NEXION?",
            "",
        ),
        (
            "What should our reorder point be for ARC-4471 at Atlantis in NEXION?",
            "unknown site",
        ),
        (
            "What should our reorder point be for AB-115 at Thule in NEXION?",
            "at least 12 months",
        ),
        (
            "What should our reorder point be for ARC-4471 at Djibouti in NEXION in 2030?",
            "falls outside",
        ),
    ],
)
def test_inventory_adversarial_queries_tier_down_red(
    inventory_executor,
    query: str,
    reason_snippet: str,
):
    result = inventory_executor.try_execute(query)
    assert result is not None
    assert result.tier == "RED"
    if reason_snippet:
        assert reason_snippet in result.message.lower()

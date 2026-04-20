from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from src.query.aggregation_executor import build_default_executor
from inventory_multisite_prototype import exposure_per_site, parts_at_risk
from phase2_realmode_prototype import (
    DEFAULT_FAILURE_DB,
    DEFAULT_INSTALLED_BASE_DB,
    DEFAULT_PO_DB,
    _load_abc_tier_map,
    _load_lead_time_map,
    _open_readonly_sqlite,
    evaluate_recommendation_item,
)


@pytest.fixture
def live_inventory_executor():
    executor = build_default_executor(
        data_dir=ROOT / "data",
        aliases_yaml=ROOT / "config" / "canonical_aliases.yaml",
    )
    try:
        yield executor
    finally:
        executor.store.close()


def test_system_scope_fgd0800_nexion_is_green_with_b_tier() -> None:
    failure_conn = _open_readonly_sqlite(DEFAULT_FAILURE_DB)
    po_conn = _open_readonly_sqlite(DEFAULT_PO_DB)
    installed_conn = _open_readonly_sqlite(DEFAULT_INSTALLED_BASE_DB)
    try:
        item = {
            "id": "TEST-ABC-B",
            "query": "What should our reorder point be for FGD-0800 across all NEXION sites?",
            "tier_expected": "GREEN",
            "inventory_scope": "part_system_total",
            "expected_filters": {"part_number": "FGD-0800", "system": "NEXION", "site_token": ""},
            "expected_result": {},
        }
        actual = evaluate_recommendation_item(
            item,
            failure_conn=failure_conn,
            lead_time_map=_load_lead_time_map(po_conn),
            abc_tier_map=_load_abc_tier_map(po_conn),
            installed_base_conn=installed_conn,
            abc_enabled=True,
        )
    finally:
        failure_conn.close()
        po_conn.close()
        installed_conn.close()

    assert actual["tier_realmode"] == "GREEN"
    assert actual["abc_tier"] == "B"
    assert actual["lead_time_days"] == 14
    assert actual["realmode_value"] == 1


def test_exposure_pe44534_isto_top_site_is_ascension() -> None:
    installed_conn = _open_readonly_sqlite(DEFAULT_INSTALLED_BASE_DB)
    po_conn = _open_readonly_sqlite(DEFAULT_PO_DB)
    try:
        payload = exposure_per_site(
            installed_conn=installed_conn,
            po_conn=po_conn,
            part_number="PE44534",
            system="ISTO",
            top_n=5,
        )
    finally:
        installed_conn.close()
        po_conn.close()

    assert payload["tier"] == "GREEN"
    assert payload["summary"]["total_installed_qty"] == 19
    assert payload["rows"][0]["site_token"] == "ascension"
    assert payload["rows"][0]["installed_qty"] == 10


def test_parts_at_risk_learmonth_returns_sems3d_40536() -> None:
    failure_conn = _open_readonly_sqlite(DEFAULT_FAILURE_DB)
    installed_conn = _open_readonly_sqlite(DEFAULT_INSTALLED_BASE_DB)
    po_conn = _open_readonly_sqlite(DEFAULT_PO_DB)
    try:
        payload = parts_at_risk(
            failure_conn=failure_conn,
            installed_conn=installed_conn,
            po_conn=po_conn,
            site_token="learmonth",
            system="NEXION",
            top_n=5,
        )
    finally:
        failure_conn.close()
        installed_conn.close()
        po_conn.close()

    assert payload["tier"] == "GREEN"
    assert payload["summary"]["site_total_qty"] == 72
    assert payload["rows"][0]["part_number"] == "SEMS3D-40536"


def test_inventory_truth_pack_v3_has_50_rows() -> None:
    pack_path = ROOT / "tests" / "aggregation_benchmark" / "inventory_truth_pack_v3_2026-04-20.json"
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 50


def test_live_executor_systemwide_inventory_route_is_green(live_inventory_executor) -> None:
    result = live_inventory_executor.try_execute(
        "reorder point for FGD-0800 across all NEXION sites"
    )
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["query_mode"] == "INVENTORY"
    assert result.parsed_params["inventory_scope"] == "part_system_total"
    assert result.ranked_rows[0]["lead_time_days"] == 14
    assert result.ranked_rows[0]["abc_tier"] == "B"


def test_live_executor_exposure_route_is_aggregation_green(live_inventory_executor) -> None:
    result = live_inventory_executor.try_execute("exposure per site for PE44534")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["query_mode"] == "AGGREGATION"
    assert result.ranked_rows[0]["site_token"] == "ascension"


def test_live_executor_hostile_inventory_query_tiers_down_red(live_inventory_executor) -> None:
    result = live_inventory_executor.try_execute(
        "What should our reorder point be for SEMS3D-40536 at Learmonth in NEXION; DROP TABLE failure_events; --?"
    )
    assert result is not None
    assert result.tier == "RED"
    assert "hostile inventory input blocked" in result.message.lower()


@pytest.mark.parametrize(
    "query",
    [
        "reorder point for FGD-0800 across all NEXION sites in 2030",
        "reorder point for FGD-0800 across all NEXION sites between 2030 and 2031",
    ],
)
def test_live_executor_systemwide_future_year_queries_tier_down_red(
    live_inventory_executor,
    query: str,
) -> None:
    result = live_inventory_executor.try_execute(query)
    assert result is not None
    assert result.tier == "RED"
    assert "falls outside failure_events coverage" in result.message.lower()

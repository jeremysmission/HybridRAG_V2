from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_FAILURE_DB = Path(r"C:\HybridRAG_V2\data\index\failure_events.sqlite3")
DEFAULT_PO_DB = Path(r"C:\HybridRAG_V2_Dev\data\index\po_pricing.sqlite3")
DEFAULT_INSTALLED_BASE_DB = Path(
    r"C:\HybridRAG_V2_Dev2\data_isolated\installed_base_end_to_end.sqlite3"
)
DEFAULT_TRUTH_PACK = Path(
    r"C:\HybridRAG_V2_Dev3\tests\aggregation_benchmark\inventory_truth_pack_2026-04-19.json"
)
DEFAULT_OUTPUT = Path(
    r"C:\HybridRAG_V2_Dev3\docs\phase2_realmode_prototype_results_2026-04-20.json"
)
SERVICE_LEVEL_Z = 1.65
DEFAULT_FALLBACK_LEAD_TIME_DAYS = 90
ABC_Z_VALUES = {
    "A": 2.33,
    "B": 1.65,
    "C": 1.28,
    "UNKNOWN": 1.65,
}


MOCK_INSTALLED_BASE: dict[str, dict[str, int]] = {
    "NEXION": {
        "alpena": 5,
        "ascension": 6,
        "azores": 4,
        "djibouti": 5,
        "eglin": 7,
        "fairford": 5,
        "guam": 8,
        "hawaii": 6,
        "kwajalein": 4,
        "learmonth": 6,
        "lualualei": 7,
        "misawa": 5,
        "thule": 4,
        "vandenberg": 12,
    },
    "ISTO": {
        "ascension": 3,
        "curacao": 4,
        "djibouti": 5,
        "guam": 3,
        "kwajalein": 4,
        "thule": 2,
    },
}


@dataclass
class HistoryWindow:
    month_labels: list[str]
    month_counts: list[int]
    history_months: int
    window_months: int
    total_failures: int


def _open_readonly_sqlite(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _month_start_from_event(raw_event_date: object, raw_event_year: object) -> date | None:
    text = str(raw_event_date or "").strip()
    if len(text) >= 7 and text[4] == "-" and text[7:8] in {"", "-"}:
        try:
            return date(int(text[0:4]), int(text[5:7]), 1)
        except ValueError:
            pass
    try:
        year = int(raw_event_year) if raw_event_year is not None else None
    except (TypeError, ValueError):
        year = None
    if year is not None and 1900 <= year <= 2100:
        return date(year, 1, 1)
    return None


def _month_diff(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _add_months(value: date, delta: int) -> date:
    year = value.year + (value.month - 1 + delta) // 12
    month = (value.month - 1 + delta) % 12 + 1
    return date(year, month, 1)


def _load_truth_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_lead_time_map(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            part_number,
            AVG(lead_time_days) AS avg_lead_time_days,
            COUNT(*) AS sample_count
        FROM po_pricing
        WHERE part_number != ''
          AND lead_time_days IS NOT NULL
          AND lead_time_days > 0
        GROUP BY part_number
        """
    ).fetchall()
    return {
        str(part_number): {
            "lead_time_days": int(round(float(avg_lead_time_days or 0.0))),
            "sample_count": int(sample_count or 0),
        }
        for part_number, avg_lead_time_days, sample_count in rows
    }


def _load_abc_tier_map(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            part_number,
            SUM(COALESCE(unit_price, 0) * COALESCE(qty, 0)) AS spend
        FROM po_pricing
        WHERE part_number != ''
        GROUP BY part_number
        HAVING spend > 0
        ORDER BY spend DESC, part_number ASC
        """
    ).fetchall()
    if not rows:
        return {}
    total_parts = len(rows)
    cutoff_a = math.ceil(total_parts * 0.2)
    cutoff_b = math.ceil(total_parts * 0.5)
    out: dict[str, dict[str, Any]] = {}
    for idx, (part_number, spend) in enumerate(rows, start=1):
        if idx <= cutoff_a:
            tier = "A"
        elif idx <= cutoff_b:
            tier = "B"
        else:
            tier = "C"
        out[str(part_number)] = {
            "abc_tier": tier,
            "spend": float(spend or 0.0),
            "rank": idx,
        }
    return out


def _resolve_installed_count(
    *,
    system: str,
    site_token: str,
    inventory_scope: str = "site_total",
) -> int | None:
    site = (site_token or "").strip().lower()
    sys_name = (system or "").strip().upper()
    if inventory_scope == "part_system_total":
        if sys_name:
            total = sum(MOCK_INSTALLED_BASE.get(sys_name, {}).values())
            return total or None
        total = sum(sum(site_map.values()) for site_map in MOCK_INSTALLED_BASE.values())
        return total or None
    if not site:
        return None
    if sys_name:
        return MOCK_INSTALLED_BASE.get(sys_name, {}).get(site)
    total = sum(site_map.get(site, 0) for site_map in MOCK_INSTALLED_BASE.values())
    return total or None


def _resolve_installed_count_from_db(
    conn: sqlite3.Connection,
    *,
    part_number: str,
    system: str,
    site_token: str,
    inventory_scope: str = "site_total",
) -> int | None:
    clauses = ["quantity_at_site IS NOT NULL", "quantity_at_site > 0"]
    params: list[object] = []
    if inventory_scope == "part_system_total":
        clauses.append("part_number = ?")
        params.append(part_number)
        if system:
            clauses.append("system = ?")
            params.append(system)
    else:
        clauses.extend(["part_number != ''", "site_token = ?"])
        params.append(site_token)
        if system:
            clauses.append("system = ?")
            params.append(system)
    sql = f"""
        SELECT part_number, system, site_token, quantity_at_site, snapshot_year, snapshot_date, id
        FROM installed_base
        WHERE {' AND '.join(clauses)}
        ORDER BY part_number ASC,
                 system ASC,
                 site_token ASC,
                 COALESCE(snapshot_year, 0) DESC,
                 COALESCE(snapshot_date, '') DESC,
                 id DESC
    """
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return None
    seen: set[tuple[str, str, str]] = set()
    total = 0
    for part_value, system_value, site_value, qty, _snapshot_year, _snapshot_date, _row_id in rows:
        key = (str(part_value or ""), str(system_value or ""), str(site_value or ""))
        if key in seen:
            continue
        seen.add(key)
        total += int(qty or 0)
    return total if total > 0 else None


def _load_history(
    conn: sqlite3.Connection,
    *,
    part_number: str,
    system: str,
    site_token: str,
    trailing_months: int = 24,
    aggregate_all_sites: bool = False,
) -> HistoryWindow:
    clauses = ["part_number = ?"]
    params: list[object] = [part_number]
    if system:
        clauses.append("system = ?")
        params.append(system)
    if not aggregate_all_sites:
        clauses.append("site_token = ?")
        params.append(site_token)
    rows = conn.execute(
        f"""
        SELECT event_date, event_year
        FROM failure_events
        WHERE {" AND ".join(clauses)}
        """,
        params,
    ).fetchall()

    bucket_counts: dict[date, int] = {}
    for raw_event_date, raw_event_year in rows:
        month_start = _month_start_from_event(raw_event_date, raw_event_year)
        if month_start is None:
            continue
        bucket_counts[month_start] = bucket_counts.get(month_start, 0) + 1

    if not bucket_counts:
        return HistoryWindow(
            month_labels=[],
            month_counts=[],
            history_months=0,
            window_months=0,
            total_failures=0,
        )

    first_month = min(bucket_counts)
    last_month = max(bucket_counts)
    history_months = _month_diff(first_month, last_month) + 1
    window_months = min(max(1, int(trailing_months)), history_months)
    window_start = _add_months(last_month, -(window_months - 1))
    months = [_add_months(window_start, offset) for offset in range(window_months)]
    month_counts = [int(bucket_counts.get(month_start, 0)) for month_start in months]
    return HistoryWindow(
        month_labels=[m.strftime("%Y-%m") for m in months],
        month_counts=month_counts,
        history_months=history_months,
        window_months=window_months,
        total_failures=int(sum(month_counts)),
    )


def _compute_stub_from_truth_pack(item: dict[str, Any]) -> dict[str, Any]:
    result = item.get("expected_result") or {}
    return {
        "recommended_units": result.get("recommended_units"),
        "reorder_point": result.get("reorder_point"),
        "history_months": result.get("history_months"),
    }


def _compute_realmode_result(
    *,
    history: HistoryWindow,
    installed_count: int | None,
    lead_time_days: int,
    service_level_z: float,
) -> dict[str, Any]:
    if history.history_months < 12:
        return {
            "tier": "RED",
            "reason": f"inventory recommender needs at least 12 months of history; found {history.history_months}",
        }
    if not installed_count or installed_count <= 0:
        return {
            "tier": "RED",
            "reason": "installed base unavailable for requested system/site mock pair",
        }

    annualized_failures_per_unit = 0.0
    if history.window_months > 0:
        annualized_failures_per_unit = (
            history.total_failures * (12.0 / history.window_months)
        ) / float(installed_count)
    daily_demand_rate = annualized_failures_per_unit / 365.0
    normalized_month_counts = [count / float(installed_count) for count in history.month_counts]
    monthly_sigma = (
        float(statistics.stdev(normalized_month_counts))
        if len(normalized_month_counts) >= 2 else 0.0
    )
    safety_stock = service_level_z * monthly_sigma * math.sqrt(lead_time_days)
    reorder_point = (daily_demand_rate * lead_time_days) + safety_stock
    recommended_units = max(1, math.ceil(reorder_point))
    tier = "GREEN" if history.history_months >= 24 else "YELLOW"
    return {
        "tier": tier,
        "daily_demand_rate": daily_demand_rate,
        "monthly_sigma": monthly_sigma,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "recommended_units": recommended_units,
        "service_level_z": service_level_z,
    }


def evaluate_recommendation_item(
    item: dict[str, Any],
    *,
    failure_conn: sqlite3.Connection,
    lead_time_map: dict[str, dict[str, Any]],
    abc_tier_map: dict[str, dict[str, Any]],
    installed_base_conn: sqlite3.Connection | None,
    abc_enabled: bool,
) -> dict[str, Any]:
    filters = item.get("expected_filters") or {}
    part_number = str(filters.get("part_number") or "")
    system = str(filters.get("system") or "")
    site_token = str(filters.get("site_token") or "")
    inventory_scope = str(item.get("inventory_scope") or "site_total")
    aggregate_all_sites = inventory_scope == "part_system_total"

    history = _load_history(
        failure_conn,
        part_number=part_number,
        system=system,
        site_token=site_token,
        aggregate_all_sites=aggregate_all_sites,
    )
    if installed_base_conn is not None:
        installed_count = _resolve_installed_count_from_db(
            installed_base_conn,
            part_number=part_number,
            system=system,
            site_token=site_token,
            inventory_scope=inventory_scope,
        )
        installed_count_source = "live_sqlite"
    else:
        installed_count = _resolve_installed_count(
            system=system,
            site_token=site_token,
            inventory_scope=inventory_scope,
        )
        installed_count_source = "mock_map"

    lead_info = lead_time_map.get(part_number)
    if lead_info:
        lead_time_days = int(lead_info["lead_time_days"])
        lead_time_source = "po_pricing_avg_by_part"
        lead_time_sample_count = int(lead_info["sample_count"])
    else:
        lead_time_days = DEFAULT_FALLBACK_LEAD_TIME_DAYS
        lead_time_source = "fallback_90"
        lead_time_sample_count = 0

    abc_info = abc_tier_map.get(part_number)
    abc_tier = str(abc_info["abc_tier"]) if abc_info else "UNKNOWN"
    service_level_z = float(ABC_Z_VALUES[abc_tier]) if abc_enabled else SERVICE_LEVEL_Z
    stub = _compute_stub_from_truth_pack(item)
    tier_stub = str(item.get("tier_expected") or "")
    realmode = _compute_realmode_result(
        history=history,
        installed_count=installed_count,
        lead_time_days=lead_time_days,
        service_level_z=service_level_z,
    )
    tier_realmode = str(realmode["tier"])
    item_out = {
        "id": item["id"],
        "query": item["query"],
        "filters": filters,
        "inventory_scope": inventory_scope,
        "history_months": history.history_months,
        "window_months": history.window_months,
        "month_labels": history.month_labels,
        "month_counts": history.month_counts,
        "total_failures": history.total_failures,
        "installed_count": installed_count,
        "installed_count_source": installed_count_source,
        "abc_tier": abc_tier,
        "service_level_z": service_level_z,
        "abc_spend": round(float(abc_info["spend"]), 2) if abc_info else None,
        "lead_time_days": lead_time_days,
        "lead_time_source": lead_time_source,
        "lead_time_sample_count": lead_time_sample_count,
        "stub_value": stub["recommended_units"],
        "stub_reorder_point": stub["reorder_point"],
        "tier_stub": tier_stub,
        "realmode_value": realmode.get("recommended_units"),
        "realmode_reorder_point": realmode.get("reorder_point"),
        "tier_realmode": tier_realmode,
        "tier_change": f"{tier_stub}->{tier_realmode}",
        "delta": (
            None
            if stub["recommended_units"] is None or realmode.get("recommended_units") is None
            else realmode["recommended_units"] - stub["recommended_units"]
        ),
        "delta_reorder_point": (
            None
            if stub["reorder_point"] is None or realmode.get("reorder_point") is None
            else round(float(realmode["reorder_point"]) - float(stub["reorder_point"]), 6)
        ),
    }
    if "reason" in realmode:
        item_out["reason"] = realmode["reason"]
    else:
        item_out["realmode_daily_demand_rate"] = round(float(realmode["daily_demand_rate"]), 9)
        item_out["realmode_monthly_sigma"] = round(float(realmode["monthly_sigma"]), 6)
        item_out["realmode_safety_stock"] = round(float(realmode["safety_stock"]), 6)
    return item_out


def run(
    *,
    failure_db: Path,
    po_db: Path,
    truth_pack_path: Path,
    output_path: Path,
    installed_base_db: Path | None = None,
    abc_enabled: bool = False,
) -> dict[str, Any]:
    truth_pack = _load_truth_pack(truth_pack_path)
    failure_conn = _open_readonly_sqlite(failure_db)
    po_conn = _open_readonly_sqlite(po_db)
    installed_base_conn = _open_readonly_sqlite(installed_base_db) if installed_base_db else None
    try:
        lead_time_map = _load_lead_time_map(po_conn)
        abc_tier_map = _load_abc_tier_map(po_conn) if abc_enabled else {}
        items_out: list[dict[str, Any]] = []
        for item in truth_pack["items"]:
            items_out.append(
                evaluate_recommendation_item(
                    item,
                    failure_conn=failure_conn,
                    lead_time_map=lead_time_map,
                    abc_tier_map=abc_tier_map,
                    installed_base_conn=installed_base_conn,
                    abc_enabled=abc_enabled,
                )
            )

        summary = {
            "item_count": len(items_out),
            "tier_stub_counts": dict(Counter(item["tier_stub"] for item in items_out)),
            "tier_realmode_counts": dict(Counter(item["tier_realmode"] for item in items_out)),
            "tier_change_counts": dict(Counter(item["tier_change"] for item in items_out)),
            "lead_time_source_counts": dict(Counter(item["lead_time_source"] for item in items_out)),
            "abc_tier_counts": dict(Counter(item["abc_tier"] for item in items_out)),
            "items_with_installed_base": sum(
                1 for item in items_out if item["installed_count"] is not None
            ),
            "installed_count_source_counts": dict(
                Counter(item["installed_count_source"] for item in items_out)
            ),
            "items_with_po_lead_time": sum(
                1 for item in items_out if item["lead_time_source"] == "po_pricing_avg_by_part"
            ),
            "mean_delta_units": round(
                statistics.mean(
                    item["delta"] for item in items_out if item["delta"] is not None
                ),
                4,
            ) if any(item["delta"] is not None for item in items_out) else None,
        }
        payload = {
            "prototype": "lane4_phase2_realmode_prewire",
            "generated_at": "2026-04-20",
            "inputs": {
                "failure_db": str(failure_db),
                "po_db": str(po_db),
                "truth_pack": str(truth_pack_path),
                "installed_base_db": str(installed_base_db) if installed_base_db else None,
                "mock_installed_base_pairs": sum(len(v) for v in MOCK_INSTALLED_BASE.values()),
                "abc_enabled": abc_enabled,
            },
            "formula_notes": {
                "stub_reference": "Matches AggregationExecutor stub formula: annualized failures / 365, statistics.stdev(month_counts), Z=1.65.",
                "phase2_change": "Real-mode prototype normalizes annualized failures and monthly sigma by installed_count and swaps lead_time_days from po_pricing when available.",
                "lead_time_fallback": DEFAULT_FALLBACK_LEAD_TIME_DAYS,
                "abc_rule": "When abc_enabled, service level uses spend-rank tiers: A=2.33, B=1.65, C=1.28, UNKNOWN=1.65 fallback.",
            },
            "summary": summary,
            "items": items_out,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
    finally:
        failure_conn.close()
        po_conn.close()
        if installed_base_conn is not None:
            installed_base_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lane 4 Phase 2 real-mode prototype harness.")
    parser.add_argument("--failure-db", type=Path, default=DEFAULT_FAILURE_DB)
    parser.add_argument("--po-db", type=Path, default=DEFAULT_PO_DB)
    parser.add_argument("--truth-pack", type=Path, default=DEFAULT_TRUTH_PACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--installed-base-db", type=Path, default=None)
    parser.add_argument("--abc-enabled", action="store_true")
    args = parser.parse_args()

    payload = run(
        failure_db=args.failure_db,
        po_db=args.po_db,
        truth_pack_path=args.truth_pack,
        output_path=args.output,
        installed_base_db=args.installed_base_db,
        abc_enabled=args.abc_enabled,
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()

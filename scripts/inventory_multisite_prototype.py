from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from phase2_realmode_prototype import (
    ABC_Z_VALUES,
    DEFAULT_FAILURE_DB,
    DEFAULT_INSTALLED_BASE_DB,
    DEFAULT_PO_DB,
    DEFAULT_TRUTH_PACK,
    SERVICE_LEVEL_Z,
    _compute_realmode_result,
    _load_abc_tier_map,
    _load_history,
    _load_lead_time_map,
    _open_readonly_sqlite,
)

DEFAULT_OUTPUT = Path(
    r"C:\HybridRAG_V2_Dev3\docs\inventory_multisite_prototype_results_2026-04-20.json"
)


def _load_price_stats(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            part_number,
            AVG(COALESCE(unit_price, 0)) AS avg_unit_price,
            SUM(COALESCE(unit_price, 0) * COALESCE(qty, 0)) AS spend,
            SUM(COALESCE(qty, 0)) AS qty_sum,
            AVG(CASE WHEN lead_time_days IS NOT NULL AND lead_time_days > 0 THEN lead_time_days END) AS avg_lead_time_days
        FROM po_pricing
        WHERE part_number != ''
        GROUP BY part_number
        """
    ).fetchall()
    return {
        str(part_number): {
            "avg_unit_price": float(avg_unit_price or 0.0),
            "spend": float(spend or 0.0),
            "qty_sum": float(qty_sum or 0.0),
            "avg_lead_time_days": (
                int(round(float(avg_lead_time_days)))
                if avg_lead_time_days is not None
                else None
            ),
        }
        for part_number, avg_unit_price, spend, qty_sum, avg_lead_time_days in rows
    }


def _latest_installed_rows(
    conn: sqlite3.Connection,
    *,
    part_number: str | None = None,
    system: str | None = None,
    site_token: str | None = None,
    include_blank_site: bool = False,
) -> list[sqlite3.Row]:
    clauses = ["part_number != ''", "quantity_at_site IS NOT NULL", "quantity_at_site > 0"]
    params: list[object] = []
    if part_number:
        clauses.append("part_number = ?")
        params.append(part_number)
    if system:
        clauses.append("system = ?")
        params.append(system)
    if site_token:
        clauses.append("site_token = ?")
        params.append(site_token)
    if not include_blank_site:
        clauses.append("site_token != ''")
    sql = f"""
        WITH ranked AS (
            SELECT
                id,
                part_number,
                system,
                site_token,
                quantity_at_site,
                snapshot_year,
                snapshot_date,
                source_path,
                ROW_NUMBER() OVER (
                    PARTITION BY part_number, system, site_token
                    ORDER BY COALESCE(snapshot_year, 0) DESC,
                             COALESCE(snapshot_date, '') DESC,
                             id DESC
                ) AS rn
            FROM installed_base
            WHERE {' AND '.join(clauses)}
        )
        SELECT id, part_number, system, site_token, quantity_at_site, snapshot_year, snapshot_date, source_path
        FROM ranked
        WHERE rn = 1
    """
    conn.row_factory = sqlite3.Row
    return conn.execute(sql, params).fetchall()


def _site_total_map(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    rows = _latest_installed_rows(conn)
    totals: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (str(row["system"] or ""), str(row["site_token"] or ""))
        totals[key] = totals.get(key, 0) + int(row["quantity_at_site"] or 0)
    return totals


def _stock_proxy_map(conn: sqlite3.Connection) -> dict[tuple[str, str, str], dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            part_number,
            system,
            site_token,
            SUM(COALESCE(qty, 0)) AS ordered_qty,
            AVG(COALESCE(unit_price, 0)) AS avg_unit_price
        FROM po_pricing
        WHERE part_number != ''
        GROUP BY part_number, system, site_token
        """
    ).fetchall()
    return {
        (str(part_number or ""), str(system or ""), str(site_token or "")): {
            "ordered_qty": float(ordered_qty or 0.0),
            "avg_unit_price": float(avg_unit_price or 0.0),
        }
        for part_number, system, site_token, ordered_qty, avg_unit_price in rows
    }


def exposure_per_site(
    *,
    installed_conn: sqlite3.Connection,
    po_conn: sqlite3.Connection,
    part_number: str,
    system: str = "",
    top_n: int = 10,
) -> dict[str, Any]:
    price_stats = _load_price_stats(po_conn)
    abc_tiers = _load_abc_tier_map(po_conn)
    rows = _latest_installed_rows(
        installed_conn,
        part_number=part_number,
        system=system or None,
        include_blank_site=False,
    )
    price = price_stats.get(part_number, {})
    avg_unit_price = float(price.get("avg_unit_price") or 0.0)
    lead_time_days = price.get("avg_lead_time_days")
    abc_tier = str(abc_tiers.get(part_number, {}).get("abc_tier") or "UNKNOWN")

    ranked_rows: list[dict[str, Any]] = []
    total_installed_qty = 0
    total_exposure_cost = 0.0
    for row in rows:
        qty = int(row["quantity_at_site"] or 0)
        total_installed_qty += qty
        exposure_cost = qty * avg_unit_price
        total_exposure_cost += exposure_cost
        ranked_rows.append(
            {
                "part_number": part_number,
                "system": str(row["system"] or ""),
                "site_token": str(row["site_token"] or ""),
                "installed_qty": qty,
                "avg_unit_price": round(avg_unit_price, 2),
                "lead_time_days": lead_time_days,
                "abc_tier": abc_tier,
                "exposure_cost": round(exposure_cost, 2),
                "source_path": str(row["source_path"] or ""),
            }
        )
    ranked_rows.sort(key=lambda row: (-row["exposure_cost"], -row["installed_qty"], row["site_token"]))
    return {
        "tier": "GREEN" if ranked_rows else "RED",
        "reason": "" if ranked_rows else "installed base unavailable for requested part/system",
        "summary": {
            "part_number": part_number,
            "system": system,
            "abc_tier": abc_tier,
            "lead_time_days": lead_time_days,
            "avg_unit_price": round(avg_unit_price, 2),
            "site_count": len(ranked_rows),
            "total_installed_qty": total_installed_qty,
            "total_exposure_cost": round(total_exposure_cost, 2),
        },
        "rows": ranked_rows[:top_n],
    }


def parts_at_risk(
    *,
    failure_conn: sqlite3.Connection,
    installed_conn: sqlite3.Connection,
    po_conn: sqlite3.Connection,
    site_token: str,
    system: str = "",
    top_n: int = 10,
    abc_enabled: bool = True,
) -> dict[str, Any]:
    site_totals = _site_total_map(installed_conn)
    site_total = site_totals.get((system, site_token))
    if not site_total:
        return {
            "tier": "RED",
            "reason": "installed base unavailable for requested site/system",
            "summary": {"site_token": site_token, "system": system, "site_total_qty": 0},
            "rows": [],
        }

    lead_time_map = _load_lead_time_map(po_conn)
    abc_tier_map = _load_abc_tier_map(po_conn) if abc_enabled else {}
    stock_proxy_map = _stock_proxy_map(po_conn)
    failure_conn.row_factory = sqlite3.Row
    part_rows = failure_conn.execute(
        """
        SELECT DISTINCT part_number
        FROM failure_events
        WHERE site_token = ?
          AND part_number != ''
          AND (? = '' OR system = ?)
        ORDER BY part_number ASC
        """,
        (site_token, system, system),
    ).fetchall()

    ranked_rows: list[dict[str, Any]] = []
    for row in part_rows:
        part_number = str(row["part_number"] or "")
        history = _load_history(
            failure_conn,
            part_number=part_number,
            system=system,
            site_token=site_token,
            aggregate_all_sites=False,
        )
        lead_info = lead_time_map.get(part_number)
        lead_time_days = (
            int(lead_info["lead_time_days"])
            if lead_info
            else 90
        )
        abc_info = abc_tier_map.get(part_number)
        abc_tier = str(abc_info["abc_tier"]) if abc_info else "UNKNOWN"
        service_level_z = float(ABC_Z_VALUES[abc_tier]) if abc_enabled else SERVICE_LEVEL_Z
        recommendation = _compute_realmode_result(
            history=history,
            installed_count=site_total,
            lead_time_days=lead_time_days,
            service_level_z=service_level_z,
        )
        if recommendation["tier"] == "RED":
            continue
        proxy = stock_proxy_map.get(
            (part_number, system, site_token),
            stock_proxy_map.get((part_number, system, ""), stock_proxy_map.get((part_number, "", ""), {})),
        )
        current_stock_proxy_qty = int(round(float(proxy.get("ordered_qty") or 0.0)))
        recommended_units = int(recommendation["recommended_units"])
        gap_units = recommended_units - current_stock_proxy_qty
        if gap_units <= 0:
            continue
        avg_unit_price = float(proxy.get("avg_unit_price") or 0.0)
        ranked_rows.append(
            {
                "part_number": part_number,
                "system": system,
                "site_token": site_token,
                "history_months": history.history_months,
                "recommended_units": recommended_units,
                "reorder_point": round(float(recommendation["reorder_point"]), 6),
                "current_stock_proxy_qty": current_stock_proxy_qty,
                "gap_units": gap_units,
                "site_total_installed_qty": site_total,
                "lead_time_days": lead_time_days,
                "abc_tier": abc_tier,
                "avg_unit_price": round(avg_unit_price, 2),
                "exposure_gap_cost": round(gap_units * avg_unit_price, 2),
            }
        )

    ranked_rows.sort(
        key=lambda row: (-row["gap_units"], -row["reorder_point"], -row["exposure_gap_cost"], row["part_number"])
    )
    return {
        "tier": "GREEN" if ranked_rows else "RED",
        "reason": "" if ranked_rows else "no positive risk gaps found with current stock proxy",
        "summary": {
            "site_token": site_token,
            "system": system,
            "site_total_qty": site_total,
            "candidate_count": len(ranked_rows),
        },
        "rows": ranked_rows[:top_n],
    }


def evaluate_multisite_item(
    item: dict[str, Any],
    *,
    failure_conn: sqlite3.Connection,
    installed_conn: sqlite3.Connection,
    po_conn: sqlite3.Connection,
    abc_enabled: bool = True,
) -> dict[str, Any]:
    filters = item.get("expected_filters") or {}
    shape = str(item.get("expected_shape") or "")
    if shape in {"exposure_per_site", "inventory_total_exposure"}:
        return exposure_per_site(
            installed_conn=installed_conn,
            po_conn=po_conn,
            part_number=str(filters.get("part_number") or ""),
            system=str(filters.get("system") or ""),
            top_n=5,
        )
    if shape == "parts_at_risk":
        return parts_at_risk(
            failure_conn=failure_conn,
            installed_conn=installed_conn,
            po_conn=po_conn,
            site_token=str(filters.get("site_token") or ""),
            system=str(filters.get("system") or ""),
            top_n=5,
            abc_enabled=abc_enabled,
        )
    raise ValueError(f"Unsupported multisite expected_shape: {shape}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lane 4 multi-site exposure/risk prototype.")
    parser.add_argument("--mode", choices=["exposure", "risk"], required=True)
    parser.add_argument("--part-number", default="")
    parser.add_argument("--system", default="")
    parser.add_argument("--site-token", default="")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--failure-db", type=Path, default=DEFAULT_FAILURE_DB)
    parser.add_argument("--po-db", type=Path, default=DEFAULT_PO_DB)
    parser.add_argument("--installed-base-db", type=Path, default=DEFAULT_INSTALLED_BASE_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    failure_conn = _open_readonly_sqlite(args.failure_db)
    po_conn = _open_readonly_sqlite(args.po_db)
    installed_conn = _open_readonly_sqlite(args.installed_base_db)
    try:
        if args.mode == "exposure":
            payload = exposure_per_site(
                installed_conn=installed_conn,
                po_conn=po_conn,
                part_number=args.part_number,
                system=args.system,
                top_n=args.top_n,
            )
        else:
            payload = parts_at_risk(
                failure_conn=failure_conn,
                installed_conn=installed_conn,
                po_conn=po_conn,
                site_token=args.site_token,
                system=args.system,
                top_n=args.top_n,
            )
        result = {
            "prototype": "lane4_multisite_inventory",
            "mode": args.mode,
            "inputs": {
                "part_number": args.part_number,
                "system": args.system,
                "site_token": args.site_token,
                "top_n": args.top_n,
                "truth_pack_hint": str(DEFAULT_TRUTH_PACK),
            },
            "result": payload,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        failure_conn.close()
        po_conn.close()
        installed_conn.close()


if __name__ == "__main__":
    main()

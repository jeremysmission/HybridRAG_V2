from __future__ import annotations

import sys
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.extraction.po_event_extractor import POEventExtractor
from src.query.aggregation_executor import (
    AggregationExecutor,
    AliasTables,
    detect_po_intent,
    parse_po_metric,
    parse_query_part_prefix,
    parse_query_part_number,
)
from src.store.failure_events_store import FailureEventsStore
from src.store.po_lifecycle_store import POOrder, POReceipt, POLifecycleStore
from src.store.po_pricing_store import POPricingEvent, POPricingStore


def test_detect_po_intent_spend_query():
    assert detect_po_intent("How much did we spend on ARC-4471 in 2024?")


def test_detect_po_intent_most_expensive_query():
    assert detect_po_intent("What are the most expensive parts in NEXION?")


def test_detect_po_intent_top_ordered_query():
    assert detect_po_intent("top 5 ordered parts in 2021")


def test_detect_po_intent_generic_top_ordered_query():
    assert detect_po_intent("What are the top ordered parts in Guam from 2022-2025?")


def test_detect_po_intent_rejects_non_po_query():
    assert not detect_po_intent("Who is the POC for Guam?")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("How much did we spend on ARC-4471?", "total_spend"),
        ("replacement cost for ARC-4471", "replacement_cost"),
        ("Which parts had the longest lead time?", "longest_lead_time"),
        ("What are the most expensive parts?", "top_cost"),
    ],
)
def test_parse_po_metric(query, expected):
    assert parse_po_metric(query) == expected


def test_parse_query_part_number():
    assert parse_query_part_number("How much did we spend on ARC-4471 in 2024?") == "ARC-4471"


def test_parse_query_part_prefix():
    assert parse_query_part_prefix("What are the top ordered ARC family parts in NEXION from 2022-2025?") == "ARC"


def test_extract_from_path_explicit_po_price():
    extractor = POEventExtractor()
    rows = extractor.extract_from_path(
        r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Parts\TO WX29-(PO 7000335240) (ARC-4471) ($44.20)\Spec.pdf"
    )
    assert len(rows) == 1
    assert rows[0].po_number == "7000335240"
    assert rows[0].part_number == "ARC-4471"
    assert rows[0].unit_price == 44.20


def test_extract_from_path_procurement_folder_uses_contract_period_start_date():
    extractor = POEventExtractor()
    rows = extractor.extract_from_path(
        (
            r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\002 - Received"
            r"\NEXION Sustainment OY1 (1 Aug 23 - 31 Jul 24)"
            r"\WX29 (PO 5000453984) (Newark) (ARC-4471) ($388.24)\PO - 5000453984.pdf"
        )
    )
    assert len(rows) == 1
    assert rows[0].po_number == "5000453984"
    assert rows[0].po_date == "2023-08-01"


def test_extract_from_chunk_purchase_order_pdf():
    extractor = POEventExtractor()
    text = """
Purchase Order
Supplier Information
Supplier Number:     90058610
PCPC DIRECT LTD
Purchase Order No.7500163591
Date Issued 10/01/2018
Item   Material/Description Delivery Date  Total Qty   UM      Unit Price    Extended Amount
    1 09/30/2019 1 LO 7,247.54 7,247.54
SecureCRT Renewal
ITEM TEXT:
PN: SCTM-0016-0679-C
"""
    rows = extractor.extract_from_chunk(
        text=text,
        chunk_id="chunk-1",
        source_path=r"D:\CorpusTransfr\verified\IGS\3.0 Cybersecurity\Software-Config-Scripts\SecureCrt\SecureCRT purchase order.pdf",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.po_number == "7500163591"
    assert row.part_number == "SCTM-0016-0679-C"
    assert row.vendor == "PCPC DIRECT LTD"
    assert row.po_date == "2018-10-01"
    assert row.unit_price == 7247.54
    assert row.qty == 1.0
    assert row.lead_time_days == 364


def test_extract_from_chunk_quote_row():
    extractor = POEventExtractor()
    text = """
Date: 7/18/2024
Purchase Order No.7000335240
Item Description Qty Unit Price Total Price
2 Antcom 123GM1215A-XN-1 choke ring Antenna 2 $1,950.00 3,900
"""
    rows = extractor.extract_from_chunk(
        text=text,
        chunk_id="chunk-2",
        source_path=r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\001 - Open Purchases\Gio and Antenna\NGC Quote 24-07-18v2.pdf",
    )
    assert len(rows) == 1
    assert rows[0].po_number == "7000335240"
    assert rows[0].part_number == "123GM1215A-XN-1"
    assert rows[0].unit_price == 1950.0
    assert rows[0].qty == 2.0
    assert rows[0].po_date == "2024-07-18"


def test_extract_from_chunk_monthly_pr_po_filename_uses_month_start_date():
    extractor = POEventExtractor()
    text = """
Purchase Order No.5000436557
Item Description Qty Unit Price Total Price
1 ARC-4471 field replaceable unit 2 44.20 88.40
"""
    rows = extractor.extract_from_chunk(
        text=text,
        chunk_id="chunk-monthly-prpo",
        source_path=r"D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl\2024 01 PR & PO_1.xlsx",
    )
    assert len(rows) == 1
    assert rows[0].po_number == "5000436557"
    assert rows[0].po_date == "2024-01-01"


def test_extract_from_chunk_dotted_filename_uses_date():
    extractor = POEventExtractor()
    text = """
Purchase Order No.5000688472
Supplier Name: CDWG
Item Description Qty Unit Price Total Price
1 SMX2200RMLV2U 1 2270.30 2270.30
"""
    rows = extractor.extract_from_chunk(
        text=text,
        chunk_id="chunk-dotted-date",
        source_path=(
            r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\001 - Open Purchases"
            r"\PO - 5000688472, PR 3000198609 UPS ISTO(CDWG)($2,270.30)"
            r"\PO 5000688472 - 02.03.2026.pdf"
        ),
    )
    assert len(rows) == 1
    assert rows[0].po_date == "2026-02-03"


def test_extract_from_path_year_organized_shipment_folder_uses_year_start():
    extractor = POEventExtractor()
    rows = extractor.extract_from_path(
        (
            r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Shipments\2025 - Shipments"
            r"\Poland 2025 - Shipment\DD250 (PO 5000453984) (ARC-4471) ($388.24)\DD250.pdf"
        )
    )
    assert len(rows) == 1
    assert rows[0].po_date == "2025-01-01"


def test_extract_from_chunk_content_signal_allows_tmp_path():
    extractor = POEventExtractor()
    text = """
Vendor Name: ACME Industries
PO Number: 5000453984
Item Description Qty Unit Price Total Price
2 ARC-4471 field replaceable unit 2 388.24 776.48
"""
    rows = extractor.extract_from_chunk(
        text=text,
        chunk_id="chunk-tmp-path",
        source_path=r"C:\tmp\moved_purchase_order.txt",
    )
    assert len(rows) == 1
    assert rows[0].po_number == "5000453984"
    assert rows[0].vendor == "ACME Industries"
    assert rows[0].part_number == "ARC-4471"


def test_extract_from_chunk_non_candidate_path_returns_empty():
    extractor = POEventExtractor()
    rows = extractor.extract_from_chunk(
        text="random status update with no purchasing data",
        chunk_id="chunk-3",
        source_path=r"D:\CorpusTransfr\verified\IGS\random\status_update.docx",
    )
    assert rows == []


@pytest.fixture
def seeded_po_store(tmp_path):
    store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    store.insert_many(
        [
            POPricingEvent(
                po_number="5000000001",
                part_number="ARC-4471",
                unit_price=100.0,
                qty=2.0,
                po_date="2024-01-15",
                vendor="ACME",
                lead_time_days=30,
                source_path="p1",
                chunk_id="c1",
                system="NEXION",
                site_token="guam",
            ),
            POPricingEvent(
                po_number="5000000002",
                part_number="ARC-4471",
                unit_price=120.0,
                qty=1.0,
                po_date="2025-02-20",
                vendor="ACME",
                lead_time_days=45,
                source_path="p2",
                chunk_id="c2",
                system="NEXION",
                site_token="guam",
            ),
            POPricingEvent(
                po_number="5000000003",
                part_number="WR-200",
                unit_price=300.0,
                qty=1.0,
                po_date="2024-03-01",
                vendor="BETA",
                lead_time_days=10,
                source_path="p3",
                chunk_id="c3",
                system="NEXION",
                site_token="guam",
            ),
            POPricingEvent(
                po_number="7000000001",
                part_number="PS-909",
                unit_price=500.0,
                qty=3.0,
                po_date="2023-06-01",
                vendor="OMEGA",
                lead_time_days=60,
                source_path="p4",
                chunk_id="c4",
                system="ISTO",
                site_token="djibouti",
            ),
            POPricingEvent(
                po_number="7000000002",
                part_number="PS-909",
                unit_price=400.0,
                qty=1.0,
                po_date="2024-07-10",
                vendor="OMEGA",
                lead_time_days=40,
                source_path="p5",
                chunk_id="c5",
                system="ISTO",
                site_token="djibouti",
            ),
            POPricingEvent(
                po_number="5000000004",
                part_number="ZZZ-1",
                unit_price=999.0,
                qty=1.0,
                po_date="2024-09-12",
                vendor="GAMMA",
                lead_time_days=None,
                source_path="p6",
                chunk_id="c6",
                system="NEXION",
                site_token="thule",
            ),
        ]
    )
    yield store
    store.close()


def test_store_insert_many_ignores_duplicates(tmp_path):
    store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    row = POPricingEvent(
        po_number="5000000001",
        part_number="ARC-4471",
        unit_price=10.0,
        qty=1.0,
        source_path="p1",
        chunk_id="c1",
    )
    assert store.insert_many([row, row]) == 1
    assert store.count() == 1
    store.close()


def test_store_coverage_summary(seeded_po_store):
    coverage = seeded_po_store.coverage_summary()
    assert coverage["total_rows"] == 6
    assert coverage["distinct_parts"] == 4
    assert coverage["with_lead_time"] == 5


def test_store_blank_part_and_po_date_are_normalized_to_null(tmp_path):
    store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    store.insert_many(
        [
            POPricingEvent(
                po_number="5000000099",
                part_number="",
                unit_price=10.0,
                qty=1.0,
                po_date="",
                source_path="p-null",
                chunk_id="c-null",
            ),
            POPricingEvent(
                po_number="5000000100",
                part_number="ARC-4471",
                unit_price=11.0,
                qty=1.0,
                po_date="2024-01-02",
                source_path="p-real",
                chunk_id="c-real",
            ),
        ]
    )
    coverage = store.coverage_summary()
    sql = store._conn.execute(
        """
        SELECT
            COUNT(DISTINCT part_number),
            MIN(po_date),
            SUM(CASE WHEN po_date IS NULL THEN 1 ELSE 0 END)
        FROM po_pricing
        """
    ).fetchone()
    assert coverage["distinct_parts"] == 1
    assert sql[0] == 1
    assert sql[1] == "2024-01-02"
    assert sql[2] == 1
    store.close()


def test_top_n_parts_by_cost_all(seeded_po_store):
    rows = seeded_po_store.top_n_parts_by_cost(limit=4)
    assert rows[0]["part_number"] == "ZZZ-1"
    assert rows[0]["max_unit_price"] == pytest.approx(999.0)
    assert rows[1]["part_number"] == "PS-909"


def test_top_n_parts_by_cost_filters_system_and_year(seeded_po_store):
    rows = seeded_po_store.top_n_parts_by_cost(limit=5, system="NEXION", year_from=2024, year_to=2024)
    assert [row["part_number"] for row in rows] == ["ZZZ-1", "WR-200", "ARC-4471"]


def test_total_spend_on_part(seeded_po_store):
    summary = seeded_po_store.total_spend_on_part("ARC-4471")
    assert summary["row_count"] == 2
    assert summary["total_spend"] == pytest.approx(320.0)
    assert summary["avg_unit_price"] == pytest.approx(110.0)


def test_total_spend_on_part_with_filters(seeded_po_store):
    summary = seeded_po_store.total_spend_on_part("PS-909", system="ISTO", year_from=2024, year_to=2024)
    assert summary["row_count"] == 1
    assert summary["total_spend"] == pytest.approx(400.0)


def test_longest_lead_time_parts(seeded_po_store):
    rows = seeded_po_store.longest_lead_time_parts(limit=3)
    assert rows[0]["part_number"] == "PS-909"
    assert rows[0]["max_lead_time_days"] == 60
    assert rows[1]["part_number"] == "ARC-4471"


def test_evidence_for_part(seeded_po_store):
    evidence = seeded_po_store.evidence_for_part("ARC-4471", system="NEXION", site_token="guam", limit=5)
    assert len(evidence) == 2
    assert all(item["system"] == "NEXION" for item in evidence)
    assert all(item["site_token"] == "guam" for item in evidence)


def test_backfill_lead_time_from_lifecycle(tmp_path):
    pricing_store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    pricing_store.insert_many(
        [
            POPricingEvent(
                po_number="5000000010",
                part_number="ARC-4471",
                unit_price=10.0,
                qty=1.0,
                po_date="2024-01-01",
                source_path="p1",
                chunk_id="c1",
            )
        ]
    )
    lifecycle_store = POLifecycleStore(tmp_path / "po_lifecycle.sqlite3")
    lifecycle_store.insert_orders(
        [POOrder(po_number="5000000010", part_number="ARC-4471", qty_ordered=1, order_date="2024-01-01", source_path="o1")]
    )
    lifecycle_store.insert_receipts(
        [POReceipt(po_number="5000000010", part_number="ARC-4471", qty_received=1, receive_date="2024-01-06", source_path="r1")]
    )
    updates = pricing_store.backfill_lead_time_days_from_lifecycle(tmp_path / "po_lifecycle.sqlite3")
    assert updates >= 1
    assert pricing_store.longest_lead_time_parts(limit=1)[0]["max_lead_time_days"] == 5
    pricing_store.close()
    lifecycle_store.close()


def test_backfill_po_date_from_lifecycle(tmp_path):
    pricing_store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    pricing_store.insert_many(
        [
            POPricingEvent(
                po_number="5000000011",
                part_number="ARC-4471",
                unit_price=10.0,
                qty=1.0,
                po_date=None,
                source_path="p1",
                chunk_id="c1",
            ),
            POPricingEvent(
                po_number="5000000012",
                part_number=None,
                unit_price=11.0,
                qty=1.0,
                po_date=None,
                source_path="p2",
                chunk_id="c2",
            ),
        ]
    )
    lifecycle_store = POLifecycleStore(tmp_path / "po_lifecycle.sqlite3")
    lifecycle_store.insert_orders(
        [
            POOrder(
                po_number="5000000011",
                part_number="ARC-4471",
                qty_ordered=1,
                order_date="2024-01-01",
                source_path="o1",
            ),
            POOrder(
                po_number="5000000012",
                part_number="",
                qty_ordered=1,
                order_date="2024-02-02",
                source_path="o2",
            ),
        ]
    )
    updates = pricing_store.backfill_po_dates_from_lifecycle(tmp_path / "po_lifecycle.sqlite3")
    rows = pricing_store._conn.execute(
        "SELECT po_number, po_date FROM po_pricing ORDER BY po_number"
    ).fetchall()
    assert updates == 2
    assert rows == [
        ("5000000011", "2024-01-01"),
        ("5000000012", "2024-02-02"),
    ]
    pricing_store.close()
    lifecycle_store.close()


@pytest.fixture
def po_executor(tmp_path, seeded_po_store):
    failure_store = FailureEventsStore(tmp_path / "failure_events.sqlite3")
    aliases = AliasTables.load(V2_ROOT / "config" / "canonical_aliases.yaml")
    executor = AggregationExecutor(failure_store, aliases, po_store=seeded_po_store)
    yield executor
    failure_store.close()


def test_executor_top_cost_query(po_executor):
    result = po_executor.try_execute("What are the most expensive parts in ISTO from 2023-2024?")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["metric"] == "top_cost"
    assert result.ranked_rows[0]["part_number"] == "PS-909"
    assert "Deterministic PO Cost Aggregation" in result.context_text


def test_executor_total_spend_query(po_executor):
    result = po_executor.try_execute("How much did we spend on ARC-4471 in 2024-2025?")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["part_number"] == "ARC-4471"
    assert result.ranked_rows[0]["total_spend"] == pytest.approx(320.0)
    assert "Deterministic PO Spend Aggregation" in result.context_text


def test_executor_replacement_cost_query(po_executor):
    result = po_executor.try_execute("replacement cost for ARC-4471 in 2024-2025")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["metric"] == "replacement_cost"
    assert result.ranked_rows[0]["max_unit_price"] == pytest.approx(120.0)
    assert "Deterministic PO Replacement-Cost Aggregation" in result.context_text


def test_executor_replacement_cost_query_resolves_alias_site_token(po_executor):
    po_executor.po_store.insert_many(
        [
            POPricingEvent(
                po_number="5300063869",
                part_number="40543-Q6623284-17386-EDITH",
                unit_price=18438.0,
                qty=None,
                po_date="2023-08-24",
                vendor="PBJ",
                lead_time_days=None,
                source_path="proof-1",
                chunk_id="proof-c1",
                system="ISTO",
                site_token="american samoa",
            ),
            POPricingEvent(
                po_number="5300063869",
                part_number="40543-Q6623284-17386-EDITH",
                unit_price=18438.0,
                qty=None,
                po_date="2023-08-24",
                vendor="PBJ",
                lead_time_days=None,
                source_path="proof-1",
                chunk_id="proof-c2",
                system="ISTO",
                site_token="american samoa",
            ),
        ]
    )
    result = po_executor.try_execute(
        "replacement cost for 40543-Q6623284-17386-EDITH at american samoa in ISTO"
    )
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["site_token"] == "american samoa"
    assert result.ranked_rows[0]["row_count"] == 2
    assert result.ranked_rows[0]["max_unit_price"] == pytest.approx(18438.0)


def test_executor_longest_lead_time_query(po_executor):
    result = po_executor.try_execute("Which parts had the longest lead time in Guam in 2024-2025?")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["metric"] == "longest_lead_time"
    assert result.ranked_rows[0]["part_number"] == "ARC-4471"
    assert "Deterministic PO Lead-Time Aggregation" in result.context_text


def test_executor_top_ordered_query(po_executor):
    result = po_executor.try_execute("top 5 ordered parts in 2024")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["metric"] == "top_ordered"
    assert result.ranked_rows[0]["part_number"] == "ARC-4471"
    assert "Deterministic PO Ordered-Parts Aggregation" in result.context_text


def test_executor_top_ordered_query_without_numeric_top_n(po_executor):
    result = po_executor.try_execute("What are the top ordered parts in Guam from 2024-2025?")
    assert result is not None
    assert result.tier == "GREEN"
    assert result.parsed_params["metric"] == "top_ordered"


def test_executor_fuzzy_top_cost_query(po_executor):
    result = po_executor.try_execute("Most expensive ARC family items ordered from 2024-2025")
    assert result is not None
    assert result.parsed_params["metric"] == "top_cost"
    assert result.parsed_params["part_prefix"] == "ARC"


def test_executor_returns_none_for_unrelated_query(po_executor):
    assert po_executor.try_execute("Who is the POC for Guam?") is None


@pytest.mark.parametrize(
    ("query", "reason_fragment"),
    [
        ("top ordered parts in GOTHAM", "unknown system"),
        ("replacement cost for ARC-4471 at Antarctica in NEXION", "unknown site"),
        ("longest lead time parts in 2030", "outside po_pricing coverage"),
        ("replacement cost for FAKE-9999 at guam in NEXION", "not present in the po_pricing substrate"),
    ],
)
def test_executor_po_adversarial_or_unresolved_inputs_tier_down(po_executor, query, reason_fragment):
    result = po_executor.try_execute(query)
    assert result is not None
    assert result.tier == "RED"
    assert reason_fragment in result.message


def test_executor_po_hostile_sql_text_tiers_down_and_does_not_mutate_store(po_executor):
    before = po_executor.po_store.count()
    result = po_executor.try_execute("top ordered parts; DROP TABLE po_pricing; --")
    after = po_executor.po_store.count()
    assert result is not None
    assert result.tier == "RED"
    assert "hostile or non-analytical SQL text" in result.message
    assert before == after

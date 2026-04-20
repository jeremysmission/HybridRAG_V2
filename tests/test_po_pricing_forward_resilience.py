from __future__ import annotations

import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.extraction.po_event_extractor import POEventExtractor
from src.store.po_pricing_store import POPricingStore


def _seed_docs() -> list[dict[str, str]]:
    return [
        {
            "chunk_id": "seed-2018-1",
            "source_path": (
                r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\001 - Open Purchases"
                r"\SecureCRT Renewal\Purchase Order 7500163591.msg"
            ),
            "text": """
Purchase Order
Supplier Information
Supplier Number: 90058610
PCPC DIRECT LTD
Purchase Order No.7500163591
Date Issued 10/01/2018
Item   Material/Description Delivery Date  Total Qty   UM      Unit Price    Extended Amount
1 09/30/2019 1 LO 7,247.54 7,247.54
ITEM TEXT:
PN: SCTM-0016-0679-C
""",
        },
        {
            "chunk_id": "seed-2024-1",
            "source_path": (
                r"D:\CorpusTransfr\verified\IGS\10.0 Program Management\1.0 FEP\Matl"
                r"\2024 01 PR & PO.xlsx"
            ),
            "text": """
Purchase Order No.5000436557
Supplier Name: LDI
Item Description Qty Unit Price Total Price
1 ARC-4471 field replaceable unit 2 44.20 88.40
""",
        },
    ]


def _june_2025_docs() -> list[dict[str, str]]:
    return [
        {
            "chunk_id": "june-2025-1",
            "source_path": (
                r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\001 - Open Purchases"
                r"\PO - 5000999001, PR 3000999001 June Test(Acme)($125.00)"
                r"\PO 5000999001 - 06.03.2025.pdf"
            ),
            "text": """
Purchase Order No.5000999001
Vendor Name: ACME
Item Description Qty Unit Price Total Price
1 ARC-TEST-1 bracket 1 125.00 125.00
""",
        },
        {
            "chunk_id": "june-2025-2",
            "source_path": (
                r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\001 - Open Purchases"
                r"\PO - 5000999002, PR 3000999002 June Test(Beta)($225.00)"
                r"\Purchase Order 5000999002.msg"
            ),
            "text": """
Purchase Order No.5000999002
Supplier Name: BETA
Date Issued 06/14/2025
Item Description Qty Unit Price Total Price
1 ARC-TEST-2 cable 1 225.00 225.00
""",
        },
        {
            "chunk_id": "june-2025-3",
            "source_path": (
                r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\Procurement\001 - Open Purchases"
                r"\PO - 5000999003, PR 3000999003 June Test(Gamma)($325.00)"
                r"\Purchase Order 5000999003.msg"
            ),
            "text": """
Purchase Order No.5000999003
Supplier Name: GAMMA
Date Issued 06/28/2025
Item Description Qty Unit Price Total Price
1 ARC-TEST-3 controller 1 325.00 325.00
""",
        },
    ]


def _ingest_docs(store: POPricingStore, docs: list[dict[str, str]]) -> int:
    extractor = POEventExtractor()
    emitted = []
    for doc in docs:
        emitted.extend(
            extractor.extract_from_chunk(
                text=doc["text"],
                chunk_id=doc["chunk_id"],
                source_path=doc["source_path"],
            )
        )
    return store.insert_many(emitted)


def test_populate_twice_is_idempotent(tmp_path):
    store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    inserted_first = _ingest_docs(store, _seed_docs())
    count_after_first = store.count()
    inserted_second = _ingest_docs(store, _seed_docs())
    assert inserted_first == 2
    assert count_after_first == 2
    assert inserted_second == 0
    assert store.count() == count_after_first
    store.close()


def test_additive_ingestion_adds_three_new_june_2025_rows(tmp_path):
    store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    _ingest_docs(store, _seed_docs())
    before = store.count()
    inserted = _ingest_docs(store, _june_2025_docs())
    june_rows = store._conn.execute(
        "SELECT COUNT(*) FROM po_pricing WHERE po_date LIKE '2025-06-%'"
    ).fetchone()[0]
    assert inserted == 3
    assert store.count() == before + 3
    assert june_rows == 3
    store.close()


def test_2018_row_count_unchanged_after_additive_ingestion(tmp_path):
    store = POPricingStore(tmp_path / "po_pricing.sqlite3")
    _ingest_docs(store, _seed_docs())
    count_2018_before = store._conn.execute(
        "SELECT COUNT(*) FROM po_pricing WHERE po_date LIKE '2018-%'"
    ).fetchone()[0]
    _ingest_docs(store, _june_2025_docs())
    count_2018_after = store._conn.execute(
        "SELECT COUNT(*) FROM po_pricing WHERE po_date LIKE '2018-%'"
    ).fetchone()[0]
    assert count_2018_before == 1
    assert count_2018_after == count_2018_before
    store.close()

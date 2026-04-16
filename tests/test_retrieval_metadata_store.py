"""Test module for the retrieval metadata store behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_embedengine import run_metadata_backfill, summarize_retrieval_metadata
from src.store.retrieval_metadata_store import (
    RetrievalMetadataStore,
    derive_source_metadata,
    resolve_retrieval_metadata_db_path,
)


def test_derive_source_metadata_for_reference_did():
    """Verify that derive source metadata for reference did behaves the way the team expects."""
    metadata = derive_source_metadata(
        r"D:\CorpusTransfr\verified\IGS\10.0 Program Management\#GSA_OASIS\DIDs\CDRL DIDs\A002--Maintenance Service Report\DI-MGMT-80995A.pdf"
    )

    assert metadata.source_ext == ".pdf"
    assert metadata.cdrl_code == "A002"
    assert metadata.is_reference_did is True
    assert metadata.is_filed_deliverable is False


def test_derive_source_metadata_for_filed_deliverable():
    """Verify that derive source metadata for filed deliverable behaves the way the team expects."""
    metadata = derive_source_metadata(
        r"D:\CorpusTransfr\verified\IGS\1.5 enterprise program CDRLS\A001 - Corrective Action Plan\Fairford\Deliverables Report IGSI-1811 Corrective Action Plan (A001)\Deliverables Report IGSI-1811 Fairford CAP 2024-09.docx"
    )

    assert metadata.source_ext == ".docx"
    assert metadata.cdrl_code == "A001"
    assert metadata.incident_id == "IGSI-1811"
    assert metadata.site_token == "fairford"
    assert metadata.site_full_name == "Fairford"
    assert metadata.is_reference_did is False
    assert metadata.is_filed_deliverable is True


def test_derive_source_metadata_for_path_signals():
    """Verify path-derived contract/program/type/category signals are deterministic."""
    metadata = derive_source_metadata(
        r"D:\CorpusTransfr\verified\IGS\monitoring system\OY2\5.0 Logistics\Packing List\Guam\PO - 5000338041 Packing List.pdf"
    )

    assert metadata.contract_period == "OY2"
    assert metadata.program_name == "monitoring system"
    assert metadata.document_type == "Packing List"
    assert metadata.document_category == "Logistics"


def test_store_finds_source_paths_by_typed_filters(tmp_path):
    """Verify that store finds source paths by typed filters behaves the way the team expects."""
    store = RetrievalMetadataStore(tmp_path / "retrieval_metadata.sqlite3")
    chunks = [
        {
            "chunk_id": "did-1",
            "text": "Reference DID",
            "source_path": r"D:\CorpusTransfr\verified\IGS\10.0 Program Management\#GSA_OASIS\DIDs\CDRL DIDs\A002--Maintenance Service Report\DI-MGMT-80995A.pdf",
        },
        {
            "chunk_id": "cap-1",
            "text": "Filed CAP",
            "source_path": r"D:\CorpusTransfr\verified\IGS\1.5 enterprise program CDRLS\A001 - Corrective Action Plan\Fairford\Deliverables Report IGSI-1811 Corrective Action Plan (A001)\Deliverables Report IGSI-1811 Fairford CAP 2024-09.docx",
        },
        {
            "chunk_id": "po-1",
            "text": "PO record",
            "source_path": r"D:\CorpusTransfr\verified\IGS\5.0 Logistics\AssetSmart\Packing List\02_20_23\PO - 5000338041, SMX2200RMLV2U.pdf",
        },
        {
            "chunk_id": "path-1",
            "text": "Path metadata record",
            "source_path": r"D:\CorpusTransfr\verified\IGS\monitoring system\OY2\5.0 Logistics\Packing List\Guam\PO - 5000338041 Packing List.pdf",
        },
    ]
    summary = store.upsert_from_chunks(chunks)

    assert summary["source_count"] == 4
    assert store.find_source_paths(cdrl_code="A002", is_reference_did=True, limit=5) == [
        chunks[0]["source_path"]
    ]
    assert store.find_source_paths(
        cdrl_code="A001",
        incident_id="IGSI-1811",
        is_filed_deliverable=True,
        site_terms=["fairford"],
        limit=5,
    ) == [chunks[1]["source_path"]]
    assert store.find_source_paths(po_number="5000338041", limit=5) == [
        chunks[2]["source_path"],
        chunks[3]["source_path"],
    ]
    assert store.find_source_paths(
        contract_period="OY2",
        program_name="monitoring system",
        document_type="Packing List",
        document_category="Logistics",
        site_terms=["guam"],
        limit=5,
    ) == [chunks[3]["source_path"]]
    store.close()


def test_summarize_and_backfill_metadata_without_reembedding(tmp_path):
    """Verify that summarize and backfill metadata without reembedding behaves the way the team expects."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    lance_db = tmp_path / "data" / "index" / "lancedb"
    config_path.write_text(
        f"paths:\n  lance_db: \"{str(lance_db).replace('\\', '/')}\"\n",
        encoding="utf-8",
    )
    chunks = [
        {
            "chunk_id": "c1",
            "text": "Reference DID",
            "source_path": r"D:\CorpusTransfr\verified\IGS\10.0 Program Management\#GSA_OASIS\DIDs\CDRL DIDs\A002--Maintenance Service Report\DI-MGMT-80995A.pdf",
        },
        {
            "chunk_id": "c2",
            "text": "Filed CAP",
            "source_path": r"D:\CorpusTransfr\verified\IGS\1.5 enterprise program CDRLS\A001 - Corrective Action Plan\Fairford\Deliverables Report IGSI-1811 Corrective Action Plan (A001)\Deliverables Report IGSI-1811 Fairford CAP 2024-09.docx",
        },
        {
            "chunk_id": "c3",
            "text": "Packing list",
            "source_path": r"D:\CorpusTransfr\verified\IGS\monitoring system\OY2\5.0 Logistics\Packing List\Guam\PO - 5000338041 Packing List.pdf",
        },
    ]

    summary = summarize_retrieval_metadata(chunks)
    assert summary["source_count"] == 3
    assert summary["with_cdrl_code"] == 2
    assert summary["reference_dids"] == 1
    assert summary["filed_deliverables"] == 1
    assert summary["with_contract_period"] == 1
    assert summary["with_program_name"] == 1
    assert summary["with_document_type"] == 1
    assert summary["with_document_category"] == 2

    result = run_metadata_backfill(export_dir, chunks, {"chunk_count": 3}, str(config_path))
    metadata_db = resolve_retrieval_metadata_db_path(lance_db)
    store = RetrievalMetadataStore(metadata_db)

    assert result["mode"] == "metadata_only"
    assert result["metadata_summary"]["source_count"] == 3
    assert metadata_db.exists()
    assert store.count() == 3
    store.close()

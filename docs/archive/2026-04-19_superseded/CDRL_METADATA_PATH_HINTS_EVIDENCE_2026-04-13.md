# CDRL Metadata Path Hints Evidence 2026-04-13

## Purpose

Freeze the next post-clean-baseline retrieval slice before it is merged into the
mainline primary workstation repo.

This slice extends metadata path recall for CDRL-heavy queries by:

- recognizing exact deliverable IDs such as `IGSI-2553` / `IGSCC-532`
- preferring artifact-specific path cues such as `MSR`, `PBOM`, `ILSP`,
  `COM-SUM`, `ACAS Scan`, and `Cybersecurity Assessment Test Report`
- preferring `Deliverables Report` / delivered artifacts ahead of DID
  reference PDFs when the query intent is clearly "what has been delivered /
  submitted / filed"

## Files Changed

- `src/query/vector_retriever.py`
- `tests/test_candidate_pool_wiring.py`

## Why This Slice Exists

The clean Tier 1 baseline showed the biggest remaining miss concentration in
CDRL and Logistics families. The earlier metadata-path patch materially helped
shipment/site/date lookups, but several CDRL queries still landed DID reference
PDFs above the real filed deliverables.

Representative pre-slice problem:

- `PQ-103` would rank `A002--Maintenance Service Report / DI-MGMT-80995A.pdf`
  ahead of the actual filed A002 MSR artifacts
- `PQ-161` would rank `A025` DID PDFs ahead of actual COM/SUM deliverables
- exact deliverable-ID queries needed stronger direct path anchoring

## Probe Method

Direct read-only probes on the live LanceDB store using the slice code loaded
from the isolated worktree:

```powershell
@'
import os, sys
os.chdir(r'C:\HybridRAG_V2')
sys.path.insert(0, r'C:\HybridRAG_V2_SliceDev')
from src.store.lance_store import LanceStore
from src.query.embedder import Embedder
from src.query.vector_retriever import VectorRetriever
'@ | C:\HybridRAG_V2\.venv\Scripts\python.exe -
```

## Observed Top-1 Improvements

### `PQ-103`

Query:

- `Which CDRL is A002 and what maintenance service reports have been submitted under it?`

Observed top result after the slice:

- `1.5 enterprise program CDRLS\A002 - Maintenance Service Report (MSR)\Alpena-monitoring system\Deliverables Report IGSI-59 Alpena monitoring system MSR R2 (A002).docx`

Interpretation:

- real filed A002 deliverable now outranks the DID reference PDF

### `PQ-159`

Query:

- `What is the Priced Bill of Materials in CDRL A014 for the enterprise program?`

Observed top result after the slice:

- `1.5 enterprise program CDRLS\A014 - Priced Bill of Materials\47QFRA22F0009_IGSI-2233_IGS_EMSI_PBOM_2024-04-22.xlsx`

Interpretation:

- `PBOM`-style artifact path now outranks the generic A014 DID reference

### `PQ-160`

Query:

- `What is the Integrated Logistics Support Plan (CDRL A023) and what does it cover?`

Observed top result after the slice:

- `1.5 enterprise program CDRLS\A023 - Integrated Logistics Support Plan (ILS)\IGSI-XX Integrated Logistics Support Plan (ILSP) (A023).docx`

Interpretation:

- `ILSP`-specific artifact path now outranks the generic A023 DID reference

### `PQ-161`

Query:

- `What has been delivered under CDRL A025 Computer Operation Manual and Software User Manual?`

Observed top result after the slice:

- `1.5 enterprise program CDRLS\A025 - Computer Operation Manual and Software User Manual (User’s Manual)\Deliverables Repot IGSI-72 legacy monitoring system Computer Operations Manual (COM) and Software Users Manual (SUM) (A025).docx`

Interpretation:

- actual COM/SUM deliverable now outranks the A025 DID reference PDFs

### `PQ-193`

Query:

- `What was the monitoring system ACAS scan deliverable for July 2025 (IGSI-2553)?`

Observed top result after the slice:

- `1.5 enterprise program CDRLS\A027 - DAA Accreditation Support Data (ACAS Scan Results)\2025\47QFRA22F0009_IGSI-2553_DAA-Accreditation-Support-Data_ACAS-Scan_NEXION_July-2025.xlsx`

Interpretation:

- exact deliverable-ID path anchoring is working for A027 monthly scan artifacts

### `PQ-195`

Query:

- `What does the legacy monitoring system RHEL 8 Cybersecurity Assessment Test Report (IGSI-2891) cover?`

Observed top result after the slice:

- `1.5 enterprise program CDRLS\A027 - Cybersecurity Assessment Test Report\A027- Cybersecurity Assessment Test Report-RHEL 8 legacy monitoring system\47QFRA22F0009_IGSI-2891_ISTO_RHEL8_Cybersecurity_Assessment_Test_Report.xlsx`

Interpretation:

- exact deliverable-ID plus subtype hints are strong enough to land the real
  filed deliverable immediately

## Test Coverage

Verified locally in the isolated worktree:

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe -m pytest -q tests\test_candidate_pool_wiring.py tests\test_query_router.py tests\test_reranker_path_aware.py
```

Result:

- `39 passed`

## Recommended Next Step

Once the currently running post-metadata-path baseline on primary workstation finishes:

1. cherry-pick this slice into the main repo
2. rerun the 400-query baseline
3. compare the CDRL family PASS / PARTIAL / MISS deltas against the
   post-metadata-path baseline

# Sprint Slice: Workstation Deployment + Install Hardening (2026-04-16)

**Owner:** Jeremy Randall (HybridRAG_V2)
**Repo:** HybridRAG_V2, CorpusForge
**Date:** 2026-04-16 MDT
**Co-pilot:** CoPilot+
**Sprint:** Current (demo prep, May 2 target)

## Goal

Production-grade, proxy-hardened install scripts for all three GUIs and
CorpusForge so that any operator can double-click a batch file on either
work machine (RTX 3000 Pro laptop or RTX 4000 desktop, both Win 11 behind
SSL-intercepting proxy) and get a fully working system with zero manual steps.

## Motivation

Both work machines currently show "ragas not installed" in QA Workbench and
Eval GUI. pip install fails behind the corporate proxy due to SSL interception.
The main GUI and CorpusForge installs also lack proxy hardening. Until these
install scripts work behind proxy, the system cannot be deployed at work.

---

## Slice 0: Waiver Documentation (COMPLETE)

**Status:** DONE
**Owner:** Coordinator

- [x] Rev C waiver sheet with RAGAS + rapidfuzz (requests 5-6)
- [x] GREEN/YELLOW/RED color scheme by approval status
- [x] Grouped by application (V2 Core, QA/Eval GUIs, CorpusForge)
- [x] CVE audit for all packages (zero unpatched CVEs)
- [x] Oldest-safe version strategy for easier approval
- [x] Cross-reference against 922-item pre-approved software list
- [x] Copies in V2 and CorpusForge repos

**Artifacts:**
- `docs/Requested_Waivers_2026-04-16_RevC.md`
- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\WAIVER_VERSION_STRATEGY_2026-04-16.md`
- `C:\Users\jerem\HYBRIDRAG_LOCAL_ONLY\SOFTWARE_WAIVER_CROSSREF_2026-04-16.md`

---

## Slice 1: Main Query GUI Install (P0)

**Owner:** Coder
**Time:** 1-2 hours
**File:** `INSTALL_MAIN_GUI.bat` (or update existing `INSTALL_WORKSTATION.bat`)

- [ ] Add CA cert auto-export (X509Store .NET API)
- [ ] Add proxy auto-detection (env vars -> Registry -> netsh)
- [ ] Generate pip.ini with proxy + cert + trusted-host
- [ ] HF_HUB_OFFLINE=1 to skip HuggingFace retries behind proxy
- [ ] Pre-flight: Python, CUDA, disk space
- [ ] Post-install: import verification for all core packages
- [ ] Operator pause points with status messages
- [ ] Install manifest / inventory output

**Test:** Fresh .venv with HTTPS_PROXY set on Beast. Main GUI launches and queries work.

---

## Slice 2: QA Workbench Install (P0)

**Owner:** Coder
**Time:** 1-2 hours
**File:** `INSTALL_QA_WORKBENCH.bat`

Includes everything in Slice 1 PLUS:
- [ ] ragas (pinned to waiver version)
- [ ] rapidfuzz (pinned to waiver version)
- [ ] All RAGAS transitive dependencies
- [ ] `requirements_qa_workbench.txt` with pinned versions
- [ ] Post-install: `python -c "import ragas; print(ragas.__version__)"` passes
- [ ] Post-install: RAGAS tab no longer shows "not installed"

**Test:** Fresh .venv with HTTPS_PROXY set. QA Workbench opens, RAGAS tab works, analysis-only runs.

---

## Slice 3: Eval GUI Install (P0)

**Owner:** Coder
**Time:** 30 min (shares requirements with Slice 2)
**File:** `INSTALL_EVAL_GUI.bat`

- [ ] Same requirements as QA Workbench (shared `requirements_eval.txt`)
- [ ] Separate batch file for independent deployment
- [ ] Post-install: Eval GUI opens, RAGAS tab works

**Test:** Fresh .venv with HTTPS_PROXY set. Eval GUI opens, all 8 tabs functional.

---

## Slice 4: CorpusForge Install (P1)

**Owner:** Coder
**Time:** 1 hour
**File:** `C:\CorpusForge\INSTALL_CORPUSFORGE.bat` (create or update)

- [ ] Same proxy hardening pattern as Slices 1-3
- [ ] CorpusForge-specific dependencies (torch for GPU embedding)
- [ ] CUDA detection and torch+cu128 install
- [ ] Post-install: pipeline import test

**Benchmark tool decision:** CorpusForge is an ingest pipeline, not a query system.
It does NOT need its own RAGAS/eval GUI. Quality measurement happens downstream in V2.
CorpusForge needs: pipeline health checks, chunk count verification, export integrity
audit. These already exist as CLI scripts (`scripts/canonical_rebuild_preflight.py`).
No new benchmark GUI needed for CorpusForge.

---

## Slice 5: Version Downgrade Validation (P1)

**Owner:** Coder
**Time:** 1-2 hours

- [ ] Create fresh .venv in `C:\HybridRAG_V2_version_test\`
- [ ] Install ALL packages at the oldest-safe waiver versions (not latest)
- [ ] Run full 50-query production eval -- compare results to Beast baseline
- [ ] Run RAGAS analysis-only -- verify metrics compute correctly
- [ ] Run regression suite -- 50 frozen patterns must pass
- [ ] Document any version incompatibilities
- [ ] If a package breaks at the waiver version, bump to minimum working version

**Acceptance:** All tests pass at pinned waiver versions. Version compatibility confirmed.

---

## Slice 6: Sanitize "3090" References (P0 -- compliance)

**Owner:** Coder
**Time:** 30 min

- [ ] Search all docs/, output/, tests/ for "3090" / "NVIDIA workstation GPU" / "GeForce NVIDIA workstation GPU"
- [ ] Replace with "NVIDIA workstation GPU" or "NVIDIA workstation desktop/laptop GPU"
- [ ] Add "3090" to sanitizer pattern list for future push safety
- [ ] Verify no 3090 references in any file the GUIs display

---

## Slice 7: LanceDB Import RAM Investigation (P1)

**Owner:** QA / Coder
**Time:** 1-2 hours

- [ ] Investigate why import loads RAM equal to GPU VRAM amount
- [ ] Check `scripts/import_embedengine.py` for numpy full-array loading
- [ ] Fix streaming/batching if possible
- [ ] Fix GUI label that displays RAM as VRAM
- [ ] Test on Beast with nvidia-smi monitoring during import

---

## Slice 8: Install Guides (P1)

**Owner:** Coder
**Time:** 1 hour

- [ ] `docs/INSTALL_AUTOMATED_GUIDE.md` -- "double-click this bat" with expected output
- [ ] `docs/INSTALL_MANUAL_GUIDE.md` -- step-by-step operator manual install in correct order
- [ ] Cover all three GUIs + CorpusForge
- [ ] Proxy troubleshooting section
- [ ] Match professional formatting (Calibri/Segoe UI template)

---

## Timeline

| Slice | Description | Priority | Est. Time | Dependency |
|-------|-------------|----------|-----------|------------|
| 0 | Waiver docs | P0 | DONE | None |
| 1 | Main GUI install | P0 | 1-2h | None |
| 2 | QA Workbench install | P0 | 1-2h | None |
| 3 | Eval GUI install | P0 | 30min | Slice 2 (shared reqs) |
| 4 | CorpusForge install | P1 | 1h | None |
| 5 | Version downgrade test | P1 | 1-2h | Slices 1-3 |
| 6 | Sanitize 3090 refs | P0 | 30min | None |
| 7 | RAM investigation | P1 | 1-2h | None |
| 8 | Install guides | P1 | 1h | Slices 1-4 |

**Can parallelize:** Slices 1+2+6 (no deps). Then 3 after 2. Then 5 after 1-3. Slice 7 independent.

---

## Work Machines Reference

| Machine | GPU | VRAM | CUDA | OS |
|---------|-----|------|------|-----|
| Workstation Laptop | RTX 3000 Pro Blackwell | 12 GB | Yes | Windows 11 |
| Workstation Desktop | RTX 4000 Blackwell | 20 GB | Yes | Windows 11 |

Both behind corporate SSL-intercepting proxy. Both have Anaconda (pre-approved).

---

Jeremy Randall | HybridRAG_V2 | 2026-04-16 MDT

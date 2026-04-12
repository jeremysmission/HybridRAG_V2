# SUPERSEDED — pylance is NOT required

**Updated:** 2026-04-11 (evening)
**Original severity:** Thought to be blocking
**Actual status:** False alarm caused by silent fallback in streaming code

## What actually happened

Agent 1's Round 3 Tier 2 memory fix discovered that the streaming chunk iteration bug was caused by a silent `except: pass` that fell back to `load_chunks()` when the optional `pylance` package wasn't available. The fix was NOT to install pylance — it was to switch the streaming code to `lancedb.SearchBuilder.to_batches()`, which is built into `lancedb` itself (version 0.30+, already in requirements.txt) and does not depend on pylance at all.

**Conclusion:** pylance is NOT a required dependency for V2. Installing it is harmless but pointless. The real fix is Agent 1's Round 3 commit to `scripts/tiered_extract.py` which uses lancedb's own streaming API.

## What to do instead

1. Pull the latest V2 (includes Agent 1's Round 3 fix at commit `8a1531b`).
2. Run `scripts/verify_install.py` — it checks every critical dependency (torch, lancedb, numpy, pyarrow, sentence_transformers, gliner, openai, fastapi, lxml) AND confirms `lancedb.LanceQueryBuilder.to_batches` exists:

   ```
   .venv\Scripts\python.exe scripts\verify_install.py
   ```

3. Exit code `0` means the install is healthy. Exit code `1` prints per-package `[OK]` / `[MISSING]` / `[FAIL]` lines and a recovery hint (typically `pip install -r requirements.txt`).
4. `INSTALL_CUDA_TORCH_WORKSTATION.bat` now calls `verify_install.py` as its Step 7/7 and auto-recovers once via `pip install -r requirements.txt` before hard-failing. Fresh workstation installs surface broken dependencies at install time rather than at runtime during a demo.
5. The pytest regression test `tests/test_critical_imports.py` runs the same checks, so CI also catches a drifted `requirements.txt`.

**Permanent solution:** `scripts/verify_install.py` is the canonical place to add new dependency checks. If the extraction or query path gains a new hard dep, add it to `CRITICAL_IMPORTS` in that script and update `test_critical_imports.py::test_critical_imports_spec_membership` — both will light up the next time a fresh workstation runs the installer or anyone runs the test suite.

**Why not add pylance anyway, just to be safe?** Because silent-fallback smells compound. If pylance were in `requirements.txt` as a "belt and suspenders" measure, nobody would bother switching to `SearchBuilder.to_batches` and the next person to debug a streaming issue would walk right into the same trap. Adding dead deps hides the real contract.

## Historical content below

The text below is preserved for context but is no longer accurate guidance.

---

# CRITICAL — pylance MUST Be Installed On Workstation Desktop Before Running Extraction

**Date:** 2026-04-11
**Severity:** BLOCKING — will silently OOM or run glacially slow if skipped
**Applies to:** workstation desktop, workstation laptop, any V2 installation

---

## The Problem

The V2 streaming chunk extraction path (`scripts/tiered_extract.py::iter_chunk_batches`) depends on the `lance` Python package. If `lance` is NOT importable from the V2 venv, the function silently falls back to `load_chunks()` which loads all 10.4M chunks into memory at once.

On a 10.4M chunk corpus, this causes:

- Peak RAM >30 GB just for the chunk list
- Tier 2 GLiNER then needs another 20+ GB on top
- Total peak >55 GB — OOMs any machine with less RAM headroom
- On 64 GB machines, it paging thrashes and takes hours longer than it should
- Entity extraction may crash partway through with no clear error

This bug hid on Beast and the workstation laptop today (2026-04-11) and was only caught when Agent 1 explicitly checked `import lance` and it failed.

## The Fix

Before running ANY extraction workflow on a fresh or existing V2 install, verify pylance is present:

```
C:\HybridRAG_V2\.venv\Scripts\python.exe -c "import lance"
```

Expected outcomes:

- **No output, new prompt** → installed, you're good
- **ModuleNotFoundError** → STOP. Install before running extraction.

If missing, install with:

```
C:\HybridRAG_V2\.venv\Scripts\pip.exe install pylance
```

Behind corporate proxy:

```
C:\HybridRAG_V2\.venv\Scripts\pip.exe install pylance --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

After install, re-verify:

```
C:\HybridRAG_V2\.venv\Scripts\python.exe -c "import lance; print(lance.__version__)"
```

## Workstation Desktop — ACTION REQUIRED

**Before the unattended 24-48h extraction run, verify pylance is installed.**

Steps (can be done in under 2 minutes):

1. Open command prompt
2. `C:\HybridRAG_V2\.venv\Scripts\python.exe -c "import lance"`
3. If error → run `C:\HybridRAG_V2\.venv\Scripts\pip.exe install pylance` (add proxy flags if needed)
4. Re-verify with step 2
5. Only then launch `RUN_IMPORT_AND_EXTRACT_GUI.bat`

Skipping this check risks:

- Silent OOM partway through the overnight run
- All extraction work lost
- Need to restart from scratch with a clean memory state

## Why This Isn't Automatic Yet

`pylance` was not in `requirements.txt` because it was pulled in implicitly on Beast via other packages. Work machines with slightly different environments do not get it. Agent 1 is adding it to the dependency list as part of the Tier 2 memory fix, but until that push lands and propagates to every machine, manual verification is required.

## Detection Commands

Quick audit of any V2 install:

```
cd C:\HybridRAG_V2
.venv\Scripts\python.exe -c "
import sys
checks = ['lance', 'lancedb', 'torch', 'numpy', 'sentence_transformers', 'gliner']
for m in checks:
    try:
        mod = __import__(m)
        v = getattr(mod, '__version__', 'present')
        print(f'  OK  {m}: {v}')
    except ImportError:
        print(f'  ** MISSING ** {m}')
"
```

All six should show OK before running extraction.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-11 MDT

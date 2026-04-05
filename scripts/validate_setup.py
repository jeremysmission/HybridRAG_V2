"""HybridRAG V2 -- Setup Validation. Run first on any new machine."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this script, or cwd)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"

results: list[dict] = []


def record(level: str, label: str, detail: str = ""):
    results.append({"level": level, "label": label, "detail": detail})


def mask_key(key: str) -> str:
    """Show first 5 and last 2 chars, mask the rest."""
    if len(key) <= 8:
        return key[:2] + "..." + key[-1:]
    return key[:5] + "..." + key[-2:]


# ===================================================================
# Individual checks
# ===================================================================

def check_python_version():
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor in (11, 12):
        record(PASS, "Python", version_str)
    elif v.major == 3 and v.minor == 14:
        record(FAIL, "Python",
               f"{version_str} — Python 3.14 is NOT supported. Use 3.11 or 3.12.")
    else:
        record(FAIL, "Python",
               f"{version_str} — Requires 3.11 or 3.12")


def check_venv():
    venv = os.environ.get("VIRTUAL_ENV", "")
    if venv:
        name = Path(venv).name
        record(PASS, "Virtual environment", f"active ({name})")
    else:
        record(WARN, "Virtual environment",
               "not active — activate .venv before running")


def check_core_packages():
    packages = {
        "openai": "openai",
        "pydantic": "pydantic",
        "yaml": "pyyaml",
        "fastapi": "fastapi",
        "numpy": "numpy",
        "httpx": "httpx",
    }
    missing = []
    for mod, label in packages.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(label)
    if not missing:
        record(PASS, "Core packages", ", ".join(packages.values()))
    else:
        record(FAIL, "Core packages",
               f"missing: {', '.join(missing)} — run: pip install -r requirements.txt")


def check_torch_cuda():
    try:
        import torch
        ver = torch.__version__
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_gb = vram_bytes / (1024 ** 3)
            record(PASS, "PyTorch + CUDA",
                   f"{ver}, CUDA available, GPU: {gpu} ({vram_gb:.0f}GB)")
        else:
            record(WARN, "PyTorch + CUDA",
                   f"{ver} installed but CUDA not available — GPU embedding disabled")
    except ImportError:
        record(FAIL, "PyTorch",
               "not installed — run: pip install torch --index-url "
               "https://download.pytorch.org/whl/cu128")


def check_sentence_transformers():
    try:
        import sentence_transformers
        ver = getattr(sentence_transformers, "__version__", "unknown")
        record(PASS, "sentence-transformers", ver)
    except ImportError:
        record(FAIL, "sentence-transformers",
               "not installed — run: pip install sentence-transformers==4.1.0")


def check_lancedb():
    try:
        import lancedb
        ver = getattr(lancedb, "__version__", "unknown")
        record(PASS, "LanceDB", ver)
    except ImportError:
        record(FAIL, "LanceDB",
               "not installed — run: pip install lancedb==0.30.2")


def check_flashrank():
    try:
        import flashrank  # noqa: F401
        record(PASS, "FlashRank", "installed")
    except ImportError:
        record(WARN, "FlashRank",
               "not installed (reranking will fall back to LanceDB built-in)")


def check_ollama():
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("name", "?") for m in data.get("models", [])]
            if models:
                record(PASS, "Ollama",
                       f"running (models: {', '.join(models)})")
            else:
                record(WARN, "Ollama",
                       "running but no models pulled — run: ollama pull nomic-embed-text")
        else:
            record(WARN, "Ollama", f"responded with status {resp.status_code}")
    except Exception:
        # Try without httpx as fallback
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                import json as _json
                data = _json.loads(resp.read())
                models = [m.get("name", "?") for m in data.get("models", [])]
                if models:
                    record(PASS, "Ollama",
                           f"running (models: {', '.join(models)})")
                else:
                    record(WARN, "Ollama",
                           "running but no models — run: ollama pull nomic-embed-text")
        except Exception:
            record(WARN, "Ollama",
                   "not reachable at localhost:11434 — install from https://ollama.com/download")


def check_tesseract():
    path = shutil.which("tesseract")
    if path:
        try:
            out = subprocess.check_output(
                ["tesseract", "--version"], stderr=subprocess.STDOUT, timeout=10
            ).decode().strip().split("\n")[0]
            record(PASS, "Tesseract OCR", out)
        except Exception:
            record(PASS, "Tesseract OCR", f"found at {path}")
    else:
        record(FAIL, "Tesseract OCR",
               "not found — install from https://github.com/UB-Mannheim/tesseract")


def check_poppler():
    path = shutil.which("pdftoppm")
    if path:
        record(PASS, "Poppler (pdftoppm)", f"found at {path}")
    else:
        record(FAIL, "Poppler (pdftoppm)",
               "not found — install pdftoppm for PDF image conversion")


def check_api_credentials():
    # Check all the key env vars the LLM client uses
    key_vars = ["HYBRIDRAG_API_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"]
    endpoint_vars = ["HYBRIDRAG_API_ENDPOINT", "AZURE_OPENAI_ENDPOINT"]

    found_key = None
    found_key_name = None
    for var in key_vars:
        val = os.environ.get(var, "")
        if val:
            found_key = val
            found_key_name = var
            break

    # Keyring fallback
    if not found_key:
        try:
            import keyring
            val = keyring.get_password("hybridrag-v2", "azure-openai") or ""
            if val:
                found_key = val
                found_key_name = "keyring(hybridrag-v2)"
        except Exception:
            pass

    if found_key:
        record(PASS, "API key",
               f"{found_key_name} set ({mask_key(found_key)})")
    else:
        record(FAIL, "API key",
               "no API key found — set OPENAI_API_KEY or AZURE_OPENAI_API_KEY")

    # Check Azure endpoint if Azure key is set
    azure_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if azure_key:
        endpoint = None
        for var in endpoint_vars:
            val = os.environ.get(var, "")
            if val:
                endpoint = val
                break
        if endpoint:
            record(PASS, "Azure endpoint", f"set ({endpoint[:30]}...)"
                   if len(endpoint) > 30 else f"set ({endpoint})")
        else:
            record(WARN, "Azure endpoint",
                   "AZURE_OPENAI_API_KEY is set but no endpoint — set AZURE_OPENAI_ENDPOINT")


def check_config_file():
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        record(FAIL, "Config file", f"not found at {config_path}")
        return
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if isinstance(cfg, dict):
            record(PASS, "Config file", "valid")
        else:
            record(FAIL, "Config file", "parsed but not a valid mapping")
    except ImportError:
        record(WARN, "Config file",
               "exists but pyyaml not installed — cannot validate")
    except Exception as e:
        record(FAIL, "Config file", f"parse error: {e}")


def check_data_directories(fix: bool = False):
    dirs = [
        PROJECT_ROOT / "data" / "index",
        PROJECT_ROOT / "data" / "source",
    ]
    missing = []
    for d in dirs:
        if not d.exists():
            missing.append(d)

    if not missing:
        record(PASS, "Data directories", "data/index/ and data/source/ exist")
    elif fix:
        for d in missing:
            d.mkdir(parents=True, exist_ok=True)
        record(PASS, "Data directories",
               f"created missing: {', '.join(str(d.relative_to(PROJECT_ROOT)) for d in missing)}")
    else:
        names = ", ".join(str(d.relative_to(PROJECT_ROOT)) for d in missing)
        record(FAIL, "Data directories",
               f"missing: {names} — run with --fix to create")


def check_lancedb_store():
    lance_path = PROJECT_ROOT / "data" / "index" / "lancedb"
    if not lance_path.exists():
        record(INFO, "LanceDB store", "no store yet (run import_embedengine.py)")
        return
    try:
        import lancedb
        db = lancedb.connect(str(lance_path))
        try:
            tables = list(db.table_names())
        except Exception:
            tables = list(db.list_tables()) if hasattr(db, "list_tables") else []
        if not tables:
            record(INFO, "LanceDB store", "0 tables (run import_embedengine.py)")
            return
        # Try to count rows in the first table (likely "chunks")
        target = "chunks" if "chunks" in tables else tables[0]
        tbl = db.open_table(target)
        count = tbl.count_rows()
        record(INFO, "LanceDB store",
               f"{count} chunks loaded (table: {target})")
    except ImportError:
        record(INFO, "LanceDB store",
               "directory exists but lancedb not installed — cannot inspect")
    except Exception as e:
        record(WARN, "LanceDB store", f"error reading store: {e}")


def check_entity_store():
    entity_path = PROJECT_ROOT / "data" / "index" / "entities.sqlite3"
    if not entity_path.exists():
        record(INFO, "Entity store",
               "0 entities (run scripts/extract_entities.py)")
        return
    try:
        import sqlite3
        conn = sqlite3.connect(str(entity_path))
        cursor = conn.cursor()
        # Try common table names
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        if "entities" in tables:
            cursor.execute("SELECT COUNT(*) FROM entities")
            count = cursor.fetchone()[0]
            record(INFO, "Entity store", f"{count} entities")
        elif tables:
            record(INFO, "Entity store",
                   f"tables found: {', '.join(tables)} (no 'entities' table)")
        else:
            record(INFO, "Entity store",
                   "database exists but empty (run scripts/extract_entities.py)")
        conn.close()
    except Exception as e:
        record(WARN, "Entity store", f"error reading: {e}")


def check_disk_space():
    drive = PROJECT_ROOT.anchor  # e.g. "C:\\"
    try:
        usage = shutil.disk_usage(drive)
        free_gb = usage.free / (1024 ** 3)
        if free_gb >= 20:
            record(PASS, "Disk space",
                   f"{free_gb:.0f} GB free on {drive.rstrip(os.sep)}")
        elif free_gb >= 5:
            record(WARN, "Disk space",
                   f"{free_gb:.1f} GB free on {drive.rstrip(os.sep)} — recommend 20GB+")
        else:
            record(FAIL, "Disk space",
                   f"{free_gb:.1f} GB free on {drive.rstrip(os.sep)} — need at least 5GB")
    except Exception as e:
        record(WARN, "Disk space", f"could not check: {e}")


# ===================================================================
# Output formatting
# ===================================================================

LEVEL_SYMBOLS = {
    PASS: "\033[32m[PASS]\033[0m",
    FAIL: "\033[31m[FAIL]\033[0m",
    WARN: "\033[33m[WARN]\033[0m",
    INFO: "\033[36m[INFO]\033[0m",
}

# Fallback if terminal doesn't support ANSI
LEVEL_PLAIN = {
    PASS: "[PASS]",
    FAIL: "[FAIL]",
    WARN: "[WARN]",
    INFO: "[INFO]",
}


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if platform.system() == "Windows":
        # Modern Windows 10+ supports ANSI via virtual terminal
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def print_results(quiet: bool = False):
    use_color = supports_color()
    symbols = LEVEL_SYMBOLS if use_color else LEVEL_PLAIN

    print()
    print("HybridRAG V2 -- Setup Validation")
    print("=" * 40)
    print()

    for r in results:
        if quiet and r["level"] not in (FAIL, WARN):
            continue
        sym = symbols[r["level"]]
        line = f"  {sym} {r['label']}"
        if r["detail"]:
            line += f": {r['detail']}"
        print(line)

    # Summary
    counts = {PASS: 0, FAIL: 0, WARN: 0, INFO: 0}
    for r in results:
        counts[r["level"]] += 1

    print()
    parts = []
    for lvl in (PASS, FAIL, WARN, INFO):
        if counts[lvl]:
            parts.append(f"{counts[lvl]} {lvl}")
    print(f"Summary: {', '.join(parts)}")

    # Action items
    fails = [r for r in results if r["level"] == FAIL]
    if fails:
        print()
        print("Action required:")
        for f in fails:
            detail = f["detail"] or f["label"]
            print(f"  - {f['label']}: {detail}")

    print()


def print_json():
    counts = {PASS: 0, FAIL: 0, WARN: 0, INFO: 0}
    for r in results:
        counts[r["level"]] += 1

    output = {
        "checks": results,
        "summary": counts,
        "all_critical_pass": counts[FAIL] == 0,
    }
    print(json.dumps(output, indent=2))


# ===================================================================
# Main
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="HybridRAG V2 -- Setup Validation")
    parser.add_argument("--fix", action="store_true",
                        help="Attempt to auto-fix what it can (create missing dirs, etc.)")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output as JSON for automation")
    parser.add_argument("--quiet", action="store_true",
                        help="Only show failures and warnings")
    args = parser.parse_args()

    # Run all checks
    check_python_version()
    check_venv()
    check_core_packages()
    check_torch_cuda()
    check_sentence_transformers()
    check_lancedb()
    check_flashrank()
    check_ollama()
    check_tesseract()
    check_poppler()
    check_api_credentials()
    check_config_file()
    check_data_directories(fix=args.fix)
    check_lancedb_store()
    check_entity_store()
    check_disk_space()

    # Output
    if args.json_output:
        print_json()
    else:
        print_results(quiet=args.quiet)

    # Exit code
    has_fail = any(r["level"] == FAIL for r in results)
    sys.exit(1 if has_fail else 0)


if __name__ == "__main__":
    main()

"""Backward-compat shim for the HybridRAG V2 QA Workbench."""

from __future__ import annotations

import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.gui.qa_workbench import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())

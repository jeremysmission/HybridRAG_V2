"""Backward-compat shim for the HybridRAG V2 Eval GUI.

The canonical module entry point now lives at ``src.gui.eval_gui`` and is
launched via::

    .venv\\Scripts\\python.exe -m src.gui.eval_gui

Using ``-m`` keeps the GUI pinned to the launching .venv interpreter and
avoids Windows .py file-association fallbacks that can split the GUI
window under a different Python than the one that imports the panels.
This shim exists so direct-script invocation::

    .venv\\Scripts\\python.exe scripts\\eval_gui.py

still works for operators who type the path literally. It does not add
any logic of its own; it just forwards to ``src.gui.eval_gui.main``.
"""

from __future__ import annotations

import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.gui.eval_gui import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

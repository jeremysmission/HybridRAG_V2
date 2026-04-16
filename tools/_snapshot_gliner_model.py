"""Download urchade/gliner_medium-v2.1 into the HF cache pointed to by $HF_HOME.

Invoked by tools/build_gliner_offline_bundle.ps1. Keep this small — it exists
as a file (not a PS here-string) to respect the ps51_python_embed rule.
"""

from __future__ import annotations

import os
import sys

from huggingface_hub import snapshot_download


def main() -> int:
    """Parse command-line inputs and run this tool end to end."""
    hf_home = os.environ.get("HF_HOME", "")
    if not hf_home:
        print("HF_HOME is not set — refusing to download outside the bundle.", file=sys.stderr)
        return 2

    path = snapshot_download(
        repo_id="urchade/gliner_medium-v2.1",
        local_dir_use_symlinks=False,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

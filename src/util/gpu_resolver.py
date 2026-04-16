"""Resolve a requested CUDA device string against actual hardware.

Work-hardware reality: single-GPU Blackwell boxes cannot serve ``cuda:1``.
Primary workstation has dual 3090s where ``cuda:1`` is preferred because
GPU 0 usually hosts the embedding pipeline. This resolver clamps the
requested index to ``cuda:0`` when only one device exists, keeps the
dual-GPU preference intact otherwise, and aborts Tier 2 with a clear
message when CUDA is unavailable (GLiNER on CPU is too slow for prod).

Used by scripts/tiered_extract.py, scripts/benchmark_gliner.py, and the
import/extract GUI. All three must go through this function so that
single-GPU workstations do not crash with "Invalid device ordinal".
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_gliner_device(device: str) -> str | None:
    """Pick a CUDA device for GLiNER or return ``None`` if Tier 2 must abort.

    Returns:
        ``None`` - CUDA requested but unavailable. Caller should skip Tier 2.
        ``"cuda:N"`` - resolved device index, possibly clamped from the request.
        ``device`` - for non-CUDA requests (``"cpu"``), returned as-is.
    """
    import torch

    resolved = device
    if "cuda" not in device:
        return resolved

    if not torch.cuda.is_available():
        message = (
            f"CUDA requested ({device}) but not available. Aborting Tier 2. "
            "GLiNER on CPU is too slow for production. Fix CUDA or skip Tier 2."
        )
        print(f"  ERROR: {message}")
        logger.error(message)
        return None

    device_count = torch.cuda.device_count()
    requested_idx = int(device.split(":")[1]) if ":" in device else 0

    if requested_idx >= device_count:
        resolved = "cuda:0"
        message = f"{device} not available (only {device_count} GPU(s)). Using {resolved}."
        print(f"  NOTE: {message}")
        logger.warning(message)
        return resolved

    if device_count > 1 and device == "cuda:1":
        free_0 = torch.cuda.mem_get_info(0)[0]
        free_1 = torch.cuda.mem_get_info(1)[0]
        # Prefer GPU 1 for GLiNER on the dual-3090 primary workstation; only
        # move to GPU 0 when it has materially more free VRAM.
        if free_0 > free_1 * 1.5:
            resolved = "cuda:0"
            message = (
                f"GPU 0 has significantly more free VRAM "
                f"({free_0 / 1e9:.1f}GB vs {free_1 / 1e9:.1f}GB). Using {resolved}."
            )
            print(f"  NOTE: {message}")
            logger.info(message)

    return resolved

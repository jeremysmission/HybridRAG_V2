"""
GLiNER CPU vs GPU benchmark on real chunks.

Usage:
    .venv\\Scripts\\python.exe scripts/benchmark_gliner.py
"""

from __future__ import annotations

import os
import sys
import time

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

V2_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.config.schema import load_config
from src.store.lance_store import LanceStore

DIVIDER = "=" * 60
LABELS = ["PERSON", "ORGANIZATION", "SITE", "FAILURE_MODE", "DATE"]
MODEL_NAME = "urchade/gliner_medium-v2.1"
BATCH_SIZE = 8
THRESHOLD = 0.5
N_CHUNKS = 1000
MIN_CHUNK_LEN = 50


def load_chunks(store: LanceStore, limit: int) -> list[dict]:
    """Load the data needed for the benchmark gliner workflow."""
    tbl = store._table
    if tbl is None:
        return []
    columns = ["chunk_id", "text", "source_path"]
    result = tbl.search().select(columns).limit(limit).to_arrow()
    chunks = []
    for i in range(result.num_rows):
        text = str(result.column("text")[i]).strip()
        if len(text) < MIN_CHUNK_LEN:
            continue
        alpha = sum(1 for ch in text if ch.isalpha()) / max(len(text), 1)
        if alpha < 0.3:
            continue
        chunks.append({
            "chunk_id": str(result.column("chunk_id")[i]),
            "text": text[:512],
        })
    return chunks[:limit]


def run_benchmark(model, chunks: list[dict], device_label: str) -> tuple[float, int]:
    """Execute one complete stage of the workflow and return its results."""
    total_entities = 0
    t0 = time.perf_counter()
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        try:
            results = model.batch_predict_entities(
                texts, LABELS, threshold=THRESHOLD, flat_ner=True,
            )
            for ents in results:
                total_entities += len(ents)
        except Exception as e:
            print(f"  Error at batch {i}: {e}")
    elapsed = time.perf_counter() - t0
    return elapsed, total_entities


def main() -> None:
    """Parse command-line inputs and run the main benchmark gliner workflow."""
    import torch
    from gliner import GLiNER

    config = load_config("config/config.yaml")
    store = LanceStore(str(V2_ROOT / config.paths.lance_db))

    print(DIVIDER)
    print("  GLiNER CPU vs GPU Benchmark")
    print(DIVIDER)
    print(f"  Model:     {MODEL_NAME}")
    print(f"  Chunks:    {N_CHUNKS}")
    print(f"  Batch:     {BATCH_SIZE}")
    print(f"  Threshold: {THRESHOLD}")
    print(f"  Labels:    {LABELS}")
    print()

    # Load chunks
    chunks = load_chunks(store, N_CHUNKS * 2)[:N_CHUNKS]
    print(f"  Loaded {len(chunks)} filtered chunks")
    print()

    # --- CPU benchmark ---
    print("  Loading GLiNER on CPU ...")
    model_cpu = GLiNER.from_pretrained(MODEL_NAME)
    print("  Running CPU benchmark ...")
    cpu_time, cpu_entities = run_benchmark(model_cpu, chunks, "CPU")
    cpu_rate = len(chunks) / max(cpu_time, 0.001)
    print(f"  CPU: {cpu_time:.1f}s, {cpu_entities} entities, {cpu_rate:.1f} chunks/sec")
    del model_cpu
    print()

    # --- GPU benchmark ---
    from src.util.gpu_resolver import resolve_gliner_device

    requested_device = config.extraction.gliner_device
    device = resolve_gliner_device(requested_device)
    if device is None:
        print("  CUDA not available -- skipping GPU benchmark")
        store.close()
        return
    if not device.startswith("cuda"):
        # Resolver returned "cpu" (or another non-CUDA device) as-is — the GPU
        # benchmark is meaningless in that case. Exit cleanly instead of
        # calling torch.cuda.get_device_name on a CPU-only box.
        print(f"  Non-CUDA device requested ({device}) -- skipping GPU benchmark")
        store.close()
        return

    gpu_idx = int(device.split(":")[1]) if ":" in device else 0
    print(f"  Loading GLiNER on {device} ({torch.cuda.get_device_name(gpu_idx)}) ...")
    model_gpu = GLiNER.from_pretrained(MODEL_NAME)
    model_gpu = model_gpu.to(device)
    print(f"  VRAM used: {(torch.cuda.mem_get_info(gpu_idx)[1] - torch.cuda.mem_get_info(gpu_idx)[0]) // 1024 // 1024} MB")

    # Warmup
    _ = model_gpu.predict_entities("warmup text", LABELS, threshold=0.5)

    print("  Running GPU benchmark ...")
    gpu_time, gpu_entities = run_benchmark(model_gpu, chunks, device)
    gpu_rate = len(chunks) / max(gpu_time, 0.001)
    speedup = cpu_time / max(gpu_time, 0.001)
    print(f"  GPU: {gpu_time:.1f}s, {gpu_entities} entities, {gpu_rate:.1f} chunks/sec")
    print()

    # --- Summary ---
    print(DIVIDER)
    print(f"  CPU:     {cpu_rate:>8.1f} chunks/sec  ({cpu_time:.1f}s)")
    print(f"  GPU:     {gpu_rate:>8.1f} chunks/sec  ({gpu_time:.1f}s)")
    print(f"  Speedup: {speedup:>8.1f}x")
    print()

    # Time estimates for full corpus
    for corpus_size in [49_750, 312_000]:
        cpu_est = corpus_size / max(cpu_rate, 0.001) / 60
        gpu_est = corpus_size / max(gpu_rate, 0.001) / 60
        print(f"  {corpus_size:>7,} chunks: CPU ~{cpu_est:.0f} min, GPU ~{gpu_est:.0f} min")

    print(DIVIDER)
    del model_gpu
    store.close()


if __name__ == "__main__":
    main()

"""
Manage a dedicated local Ollama service for Sprint 8 demo work.

Starts a separate Ollama server on a chosen port, pins it to a single GPU,
and can preload the selected model with keep-alive enabled.

Usage:
    python scripts/manage_demo_ollama.py start
    python scripts/manage_demo_ollama.py start --gpu auto --port 11435
    python scripts/manage_demo_ollama.py status
    python scripts/manage_demo_ollama.py stop
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / "results" / "demo_ollama"


def state_path(port: int) -> Path:
    """Support the manage demo ollama workflow by handling the state path step."""
    return RUNTIME_DIR / f"demo_ollama_{port}.json"


def parse_gpu_table() -> list[dict]:
    """Read GPU memory/utilization from nvidia-smi."""
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    rows: list[dict] = []
    for line in result.stdout.splitlines():
        parts = [item.strip() for item in line.split(",")]
        if len(parts) != 4:
            continue
        rows.append(
            {
                "index": int(parts[0]),
                "name": parts[1],
                "memory_used_mib": int(parts[2]),
                "utilization_pct": int(parts[3]),
            }
        )
    if not rows:
        raise RuntimeError("No GPUs reported by nvidia-smi.")
    return rows


def choose_gpu(raw_gpu: str) -> tuple[int, list[dict]]:
    """Pick the requested GPU or the least-busy GPU."""
    rows = parse_gpu_table()
    if raw_gpu != "auto":
        gpu = int(raw_gpu)
        if gpu not in {row["index"] for row in rows}:
            raise ValueError(f"GPU {gpu} not reported by nvidia-smi.")
        return gpu, rows
    chosen = min(rows, key=lambda row: (row["memory_used_mib"], row["utilization_pct"], row["index"]))
    return int(chosen["index"]), rows


def ping_server(port: int, timeout_seconds: float = 3.0) -> bool:
    """Whether the Ollama API is reachable on the chosen port."""
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(f"http://127.0.0.1:{port}/api/version")
        return resp.status_code == 200
    except Exception:
        return False


def wait_for_server(port: int, timeout_seconds: float = 60.0) -> None:
    """Wait until the Ollama API starts responding."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if ping_server(port, timeout_seconds=2.0):
            return
        time.sleep(1.0)
    raise TimeoutError(f"Ollama did not become ready on port {port} within {timeout_seconds:.0f}s.")


def preload_model(port: int, model: str) -> dict:
    """Load the model and keep it resident for the demo window."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Respond with OK."}],
        "stream": False,
        "keep_alive": -1,
    }
    with httpx.Client(timeout=240.0) as client:
        resp = client.post(f"http://127.0.0.1:{port}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


def start_service(args: argparse.Namespace) -> int:
    """Start a detached Ollama service configured for demo use."""
    port = int(args.port)
    if ping_server(port):
        print(f"Ollama already responding on port {port}.")
        return 0

    gpu, rows = choose_gpu(args.gpu)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = RUNTIME_DIR / f"ollama_{port}.out.log"
    stderr_path = RUNTIME_DIR / f"ollama_{port}.err.log"

    env = os.environ.copy()
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    env["OLLAMA_KEEP_ALIVE"] = "-1"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"
    if args.context_length:
        env["OLLAMA_CONTEXT_LENGTH"] = str(args.context_length)

    creationflags = 0
    creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    with open(stdout_path, "a", encoding="utf-8") as stdout_handle, open(
        stderr_path, "a", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            ["ollama", "serve"],
            cwd=str(ROOT),
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
        )

    meta = {
        "pid": process.pid,
        "port": port,
        "gpu": gpu,
        "model": args.model,
        "context_length": args.context_length,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gpu_snapshot": rows,
    }
    state_path(port).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Started dedicated Ollama on port {port} using GPU {gpu} (pid {process.pid}).")
    wait_for_server(port, timeout_seconds=args.start_timeout)
    print("Ollama API is responding.")

    if not args.no_preload:
        preload = preload_model(port, args.model)
        total_duration = preload.get("total_duration", 0)
        load_duration = preload.get("load_duration", 0)
        print(
            f"Preloaded {args.model} on port {port}. "
            f"total_duration={total_duration} load_duration={load_duration}"
        )

    return 0


def read_state(port: int) -> dict | None:
    """Read a file or artifact and return it in a form later steps can use."""
    path = state_path(port)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def status_service(args: argparse.Namespace) -> int:
    """Print current state for the chosen demo Ollama port."""
    port = int(args.port)
    meta = read_state(port)
    online = ping_server(port)
    print(json.dumps({"port": port, "online": online, "state": meta}, indent=2))
    return 0 if online else 1


def stop_service(args: argparse.Namespace) -> int:
    """Stop the dedicated Ollama service if we have a recorded pid."""
    port = int(args.port)
    meta = read_state(port)
    if not meta:
        print(f"No demo Ollama state file found for port {port}.")
        return 1

    pid = int(meta["pid"])
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
    if state_path(port).exists():
        state_path(port).unlink()
    print(f"Stopped demo Ollama pid {pid} on port {port}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Assemble the structured object this workflow needs for its next step."""
    parser = argparse.ArgumentParser(description="Manage dedicated Ollama service for demo work.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start a dedicated Ollama service.")
    start.add_argument("--gpu", default="auto", help="GPU index or 'auto' (default: auto).")
    start.add_argument("--port", type=int, default=11435, help="Ollama port (default: 11435).")
    start.add_argument("--model", default="phi4:14b-q4_K_M", help="Model to preload.")
    start.add_argument(
        "--context-length",
        type=int,
        default=8192,
        help="OLLAMA_CONTEXT_LENGTH value for the dedicated service.",
    )
    start.add_argument("--start-timeout", type=float, default=60.0, help="Seconds to wait for startup.")
    start.add_argument("--no-preload", action="store_true", help="Skip the preload request.")
    start.set_defaults(func=start_service)

    status = sub.add_parser("status", help="Show status for the dedicated service.")
    status.add_argument("--port", type=int, default=11435, help="Ollama port (default: 11435).")
    status.set_defaults(func=status_service)

    stop = sub.add_parser("stop", help="Stop the dedicated service started by this script.")
    stop.add_argument("--port", type=int, default=11435, help="Ollama port (default: 11435).")
    stop.set_defaults(func=stop_service)
    return parser


def main() -> int:
    """Parse command-line inputs and run the main manage demo ollama workflow."""
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

"""Benchmark runner for checking how well the system answers aggregation-style questions against a fixed answer set."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

V2_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = (
    V2_ROOT / "tests" / "aggregation_benchmark" / "aggregation_seed_manifest_2026-04-15.json"
)


@dataclass(frozen=True)
class BenchmarkItem:
    """Structured input record that keeps one unit of work easy to pass around and inspect."""
    id: str
    family: str
    question: str
    answer_kind: str
    expected_answer: int
    scope_rule: str
    dedup_rule: str
    counting_note: str
    source_reference: str
    evidence_notes: str


@dataclass
class ItemResult:
    """Small structured record used to keep related results together as the workflow runs."""
    id: str
    family: str
    question: str
    expected_answer: int
    actual_answer: Any
    passed: bool
    detail: str


@dataclass
class BenchmarkSummary:
    """Small structured record used to keep related results together as the workflow runs."""
    benchmark_id: str
    manifest_path: str
    mode: str
    total_items: int
    pass_count: int
    fail_count: int
    pass_rate: float
    gate_pass: bool
    results: list[dict] = field(default_factory=list)


def _load_json(path: Path) -> Any:
    """Load the data needed for the run aggregation benchmark 2026 04 15 workflow."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> dict[str, Any]:
    """Load the data needed for the run aggregation benchmark 2026 04 15 workflow."""
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Manifest at {path} must be a JSON object.")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Manifest must contain a non-empty 'items' list.")

    seen: set[str] = set()
    validated_items: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError("Each manifest item must be a JSON object.")
        item_id = raw.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("Each manifest item must include a string 'id'.")
        if item_id in seen:
            raise ValueError(f"Duplicate manifest item id: {item_id}")
        seen.add(item_id)

        expected_answer = raw.get("expected_answer")
        if not isinstance(expected_answer, int):
            raise ValueError(f"Manifest item {item_id} must have an integer expected_answer.")

        validated_items.append(raw)

    data["items"] = validated_items
    return data


def load_answers(path: Path) -> dict[str, Any]:
    """Load the data needed for the run aggregation benchmark 2026 04 15 workflow."""
    raw = _load_json(path)
    if isinstance(raw, dict):
        answers: dict[str, Any] = {}
        for key, value in raw.items():
            if isinstance(value, dict) and "answer" in value:
                answers[str(key)] = value["answer"]
            else:
                answers[str(key)] = value
        return answers

    if isinstance(raw, list):
        answers = {}
        for entry in raw:
            if not isinstance(entry, dict):
                raise ValueError("Answer list entries must be objects.")
            item_id = entry.get("id")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("Each answer entry must have a string 'id'.")
            if "answer" not in entry:
                raise ValueError(f"Answer entry {item_id} missing 'answer'.")
            answers[item_id] = entry["answer"]
        return answers

    raise ValueError("Answers file must be a JSON object or array.")


def _normalize_text(value: Any) -> str:
    """Support the run aggregation benchmark 2026 04 15 workflow by handling the normalize text step."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def score_answer(expected_answer: int, actual_answer: Any) -> tuple[bool, str]:
    """Calculate a score that summarizes how well the system performed."""
    if actual_answer is None:
        return False, f"missing answer (expected {expected_answer})"

    if isinstance(actual_answer, bool):
        return False, f"boolean answer is not valid for count {expected_answer}"

    if isinstance(actual_answer, int):
        return actual_answer == expected_answer, f"numeric answer {actual_answer}"

    if isinstance(actual_answer, float) and actual_answer.is_integer():
        actual_int = int(actual_answer)
        return actual_int == expected_answer, f"numeric answer {actual_int}"

    if isinstance(actual_answer, dict) and "answer" in actual_answer:
        return score_answer(expected_answer, actual_answer["answer"])

    text = _normalize_text(actual_answer).replace(",", "").strip()
    if not text:
        return False, "empty answer text"

    if re.search(rf"(?<!\d){re.escape(str(expected_answer))}(?!\d)", text):
        return True, f"matched token {expected_answer}"

    numeric_tokens = re.findall(r"\d+", text)
    if len(numeric_tokens) == 1 and int(numeric_tokens[0]) == expected_answer:
        return True, f"single numeric token {expected_answer}"

    if numeric_tokens:
        return False, f"numeric tokens={numeric_tokens}"
    return False, f"no numeric token matched expected {expected_answer}"


def run_benchmark(
    manifest: dict[str, Any],
    answers: dict[str, Any] | None = None,
    *,
    self_check: bool = False,
    min_pass_rate: float = 1.0,
    manifest_path: Path | None = None,
) -> BenchmarkSummary:
    """Execute one complete stage of the workflow and return its results."""
    items = manifest["items"]
    answer_map = answers or {}
    results: list[ItemResult] = []

    for raw in items:
        item = BenchmarkItem(**raw)
        actual_answer = item.expected_answer if self_check and item.id not in answer_map else answer_map.get(item.id)
        passed, detail = score_answer(item.expected_answer, actual_answer)
        results.append(
            ItemResult(
                id=item.id,
                family=item.family,
                question=item.question,
                expected_answer=item.expected_answer,
                actual_answer=actual_answer,
                passed=passed,
                detail=detail,
            )
        )

    pass_count = sum(1 for result in results if result.passed)
    total_items = len(results)
    fail_count = total_items - pass_count
    pass_rate = pass_count / total_items if total_items else 0.0
    gate_pass = pass_rate >= min_pass_rate and fail_count == 0

    return BenchmarkSummary(
        benchmark_id=str(manifest.get("benchmark_id", "aggregation_benchmark")),
        manifest_path=str(manifest_path or ""),
        mode="self-check" if self_check else "score",
        total_items=total_items,
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=pass_rate,
        gate_pass=gate_pass,
        results=[asdict(result) for result in results],
    )


def _print_summary(summary: BenchmarkSummary) -> None:
    """Render a readable summary for the person running the tool."""
    print(f"Benchmark: {summary.benchmark_id}")
    print(f"Mode: {summary.mode}")
    if summary.manifest_path:
        print(f"Manifest: {summary.manifest_path}")
    print(f"Gate: {'PASS' if summary.gate_pass else 'FAIL'}")
    print(f"Score: {summary.pass_count}/{summary.total_items} ({summary.pass_rate:.3f})")
    print()

    for result in summary.results:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{status}] {result['id']} | expected={result['expected_answer']} | "
            f"actual={_normalize_text(result['actual_answer']) or '<missing>'}"
        )
        print(f"       {result['question']}")
        if not result["passed"]:
            print(f"       detail: {result['detail']}")


def _write_output(path: Path, summary: BenchmarkSummary) -> None:
    """Write the generated output so the workflow leaves behind a reusable artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(summary)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Parse command-line inputs and run the main run aggregation benchmark 2026 04 15 workflow."""
    parser = argparse.ArgumentParser(
        description="Run the frozen HybridRAG V2 aggregation benchmark seed set."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Seed manifest JSON path")
    parser.add_argument("--answers-file", default=None, help="Candidate answers JSON path")
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=1.0,
        help="Gate threshold; default is all items must pass.",
    )
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    self_check = args.answers_file is None
    answers = load_answers(Path(args.answers_file)) if args.answers_file else None

    summary = run_benchmark(
        manifest,
        answers,
        self_check=self_check,
        min_pass_rate=args.min_pass_rate,
        manifest_path=manifest_path,
    )
    _print_summary(summary)
    if args.output:
        _write_output(Path(args.output), summary)

    return 0 if summary.gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

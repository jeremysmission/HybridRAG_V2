"""Test module for the generate workstation safe eval behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_workstation_safe_eval.py"


def _write_json(path: Path, payload: object) -> None:
    """Support this test module by handling the write json step."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_generator_produces_workstation_safe_profile(tmp_path: Path) -> None:
    """Verify that generator produces workstation safe profile behaves the way the team expects."""
    canonical = tmp_path / "canonical.json"
    derived = tmp_path / "derived.json"
    validation = tmp_path / "validation.json"

    payload = [
        {
            "query_id": "PQ-900",
            "user_input": "Show me the enterprise program PMR and the monitoring system ACAS scan.",
            "reference": (
                "Use IGS_PMR_2026_FebR1.pptx and "
                "IGSI-2553_DAA-Accreditation-Support-Data_ACAS-Scan_NEXION_July-2025.xlsx."
            ),
            "reference_contexts": [
                "10.0 Program Management/6.0 PMR/2026/IGS_PMR_2026_FebR1.pptx",
                "1.5 enterprise program CDRLS/A027/IGSI-2553_DAA-Accreditation-Support-Data_ACAS-Scan_NEXION_July-2025.xlsx",
            ],
            "persona": "Program Manager",
            "expected_query_type": "SEMANTIC",
            "expected_document_family": "Program Management",
            "expected_source_patterns": ["%IGS_PMR%", "%NEXION_July-2025%"],
            "difficulty": "medium",
            "rationale": "Tests enterprise program to monitoring system handoff wording.",
            "expected_anchor_entities": {"DELIVERABLE": ["IGSI-2553", "IGSCC-532"]},
            "has_ground_truth": True,
            "corpus_grounding_evidence": (
                "Folder evidence includes IGS_PMR_2026_FebR1.pptx and "
                "2019-04-28_NEXION_Re-Authorization."
            ),
        }
    ]
    _write_json(canonical, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--canonical",
            str(canonical),
            "--output-json",
            str(derived),
            "--validation-json",
            str(validation),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    derived_rows = json.loads(derived.read_text(encoding="utf-8"))
    report = json.loads(validation.read_text(encoding="utf-8"))

    assert derived_rows[0]["user_input"] == (
        "Show me the enterprise program PMR and the monitoring system ACAS scan."
    )
    assert "enterprise-program_PMR" in derived_rows[0]["reference"]
    assert "monitoring-system_July-2025" in derived_rows[0]["reference"]
    assert derived_rows[0]["reference_contexts"][0].endswith("IGS_PMR_2026_FebR1.pptx")
    assert derived_rows[0]["expected_source_patterns"] == ["%IGS_PMR%", "%NEXION_July-2025%"]
    assert report["summary"]["disallowed_hits_in_sanitized_fields"] == 0
    assert report["summary"]["allowed_residual_hits_in_preserved_fields"] > 0


def test_validate_only_fails_when_sanitized_field_has_banned_token(tmp_path: Path) -> None:
    """Verify that validate only fails when sanitized field has banned token behaves the way the team expects."""
    derived = tmp_path / "derived.json"
    validation = tmp_path / "validation.json"
    canonical = tmp_path / "canonical.json"

    payload = [
        {
            "query_id": "PQ-901",
            "user_input": "Show me the monitoring system scan report.",
            "reference": "Safe reference.",
            "reference_contexts": [],
            "persona": "Cybersecurity",
            "expected_query_type": "ENTITY",
            "expected_document_family": "Cybersecurity",
            "expected_source_patterns": [],
            "difficulty": "easy",
            "rationale": "Safe rationale.",
            "expected_anchor_entities": {"DELIVERABLE": ["IGSI-2553"]},
            "has_ground_truth": True,
            "corpus_grounding_evidence": "Safe evidence.",
        }
    ]
    _write_json(derived, payload)
    _write_json(canonical, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--canonical",
            str(canonical),
            "--validate-only",
            "--input-json",
            str(derived),
            "--validation-json",
            str(validation),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    report = json.loads(validation.read_text(encoding="utf-8"))

    assert result.returncode == 1
    assert report["summary"]["disallowed_hits_in_sanitized_fields"] == 1
    assert report["disallowed_hits"][0]["field"] == "user_input"

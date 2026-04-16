"""Test module for the schema pattern regression behavior. The checks here explain what the repository expects to keep working."""
# ============================================================================
# tests/test_schema_pattern_regression.py
# ----------------------------------------------------------------------------
# Locks in the schema-pattern regression fixture and harness:
#   - frozen fixture file is present and well-formed
#   - rule classifier returns the expected verdict for every focus family
#   - run_fixture() reports 100% pass on the frozen fixture
#   - normalize cases also produce the correct canonical
# ============================================================================

import json
from pathlib import Path

import pytest

from src.regression.schema_pattern import (
    DEFAULT_FIXTURE_PATH,
    classify,
    discover_fixtures,
    format_oneline_summary,
    load_fixture,
    run_all_fixtures,
    run_fixture,
    validate_fixture,
)


def test_default_fixture_exists():
    """Verify that default fixture exists behaves the way the team expects."""
    assert DEFAULT_FIXTURE_PATH.exists(), DEFAULT_FIXTURE_PATH
    fixture = load_fixture()
    assert fixture["fixture_id"] == "schema_pattern_regression_2026_04_15"
    assert len(fixture["cases"]) >= 40
    assert len(fixture["families"]) == 5


@pytest.mark.parametrize(
    "etype,text,expected",
    [
        # SITE drops
        ("SITE", "WEBSITE", "drop"),
        ("SITE", "OBSOLESCENCE WEBSITE", "drop"),
        ("SITE", "facility", "drop"),
        ("SITE", "CABINET 2", "drop"),
        ("SITE", "LOCATION", "drop"),
        # SITE keeps
        ("SITE", "Peterson AFB", "keep"),
        ("SITE", "Eglin AFB", "keep"),
        # PERSON drops
        ("PERSON", "CFO", "drop"),
        ("PERSON", "root", "drop"),
        ("PERSON", "Organizational personnel", "drop"),
        ("PERSON", "users", "drop"),
        # PERSON keeps
        ("PERSON", "Jane Doe", "keep"),
        # CONTACT drops (numeric junk)
        ("CONTACT", "4294967295", "drop"),
        ("CONTACT", "3926909988", "drop"),
        # CONTACT keeps (real phone/email)
        ("CONTACT", "719-393-8115", "keep"),
        ("CONTACT", "(972) 833-0641", "keep"),
        ("CONTACT", "ryan.hamel@digisonde.com", "keep"),
        # DATE drops (header labels)
        ("DATE", "EOS DATE", "drop"),
        ("DATE", "EOL DATE", "drop"),
        ("DATE", "ACQUISITION DATE", "drop"),
        # DATE keeps (calendar values)
        ("DATE", "2015-12-27", "keep"),
        ("DATE", "17-Feb-2016", "keep"),
        ("DATE", "09/09/22", "keep"),
        # ORG drops (generic buckets)
        ("ORG", "organization", "drop"),
        ("ORG", "The organization", "drop"),
        ("ORG", "Organizations", "drop"),
        # ORG keep
        ("ORG", "monitoring system", "keep"),
    ],
)
def test_classifier_focus_families(etype, text, expected):
    """Verify that classifier focus families behaves the way the team expects."""
    action, _canon, _rule = classify(etype, text)
    assert action == expected, "classify({!r}, {!r}) -> {}".format(etype, text, action)


@pytest.mark.parametrize(
    "etype,text,canonical",
    [
        ("SITE", "Onsite", "Onsite"),
        ("SITE", "OnSite", "Onsite"),
        ("SITE", "on-site", "Onsite"),
        ("SITE", "On-Site", "Onsite"),
        ("ORG",  "MCMASTER-CARR", "McMaster-Carr"),
        ("ORG",  "McMaster-Carr", "McMaster-Carr"),
        ("PO",   "IR-4A", "IR-4A"),
        ("PO",   "IR-4a", "IR-4A"),
    ],
)
def test_classifier_normalize_clusters(etype, text, canonical):
    """Verify that classifier normalize clusters behaves the way the team expects."""
    action, canon, _rule = classify(etype, text)
    assert action == "normalize"
    assert canon == canonical


def test_run_fixture_full_pass():
    """Verify that run fixture full pass behaves the way the team expects."""
    report = run_fixture()
    assert report.failed == 0, [v.case_id for v in report.verdicts if not v.passed]
    assert report.passed == report.total
    # Expect coverage across all 5 focus families.
    fam_names = {f.family for f in report.families}
    assert {
        "site_generic_placeholder_labels",
        "person_role_common_noun_leakage",
        "contact_numeric_junk_split",
        "date_header_label_leakage",
        "org_generic_bucket_and_case",
    } <= fam_names


def test_panel_registry_includes_regression_lane():
    """Verify that panel registry includes regression lane behaves the way the team expects."""
    from src.gui.panels.panel_registry import get_panels

    keys = [p.key for p in get_panels()]
    assert "regression" in keys


# ---------------------------------------------------------------------------
# Fixture schema integrity (fallback test-coverage pass)
# ---------------------------------------------------------------------------

_VALID_ACTIONS = {"keep", "drop", "normalize"}
_FOCUS_FAMILIES = {
    "site_generic_placeholder_labels",
    "person_role_common_noun_leakage",
    "contact_numeric_junk_split",
    "date_header_label_leakage",
    "org_generic_bucket_and_case",
}
_REQUIRED_CASE_KEYS = {"id", "family", "text", "entity_type", "expected"}


def test_fixture_top_level_schema():
    """Verify that fixture top level schema behaves the way the team expects."""
    fixture = load_fixture()
    for key in ("fixture_id", "frozen_at", "store_snapshot", "families", "cases", "normalization_clusters"):
        assert key in fixture, "fixture missing top-level key: {}".format(key)
    assert fixture["frozen_at"] == "2026-04-15"
    assert isinstance(fixture["cases"], list) and fixture["cases"]


def test_fixture_case_records_well_formed():
    """Verify that fixture case records well formed behaves the way the team expects."""
    fixture = load_fixture()
    seen_ids: set[str] = set()
    for case in fixture["cases"]:
        missing = _REQUIRED_CASE_KEYS - set(case.keys())
        assert not missing, "case missing keys {}: {}".format(missing, case.get("id"))
        assert case["expected"] in _VALID_ACTIONS, case
        assert case["family"] in _FOCUS_FAMILIES, case
        assert case["entity_type"] == case["entity_type"].upper(), case
        assert case["id"] not in seen_ids, "duplicate case id: {}".format(case["id"])
        seen_ids.add(case["id"])
        if case["expected"] == "normalize":
            assert case.get("canonical"), "normalize case missing canonical: {}".format(case["id"])


def test_fixture_normalize_clusters_reference_real_canonicals():
    """Verify that fixture normalize clusters reference real canonicals behaves the way the team expects."""
    fixture = load_fixture()
    cluster_canonicals = {(c["entity_type"], c["canonical"]) for c in fixture["normalization_clusters"]}
    case_canonicals = {
        (c["entity_type"], c["canonical"])
        for c in fixture["cases"] if c["expected"] == "normalize"
    }
    # Every case canonical must appear in the cluster declarations.
    assert case_canonicals <= cluster_canonicals, case_canonicals - cluster_canonicals


def test_fixture_focus_family_coverage_minimums():
    """Verify that fixture focus family coverage minimums behaves the way the team expects."""
    fixture = load_fixture()
    by_family: dict[str, list[dict]] = {}
    for case in fixture["cases"]:
        by_family.setdefault(case["family"], []).append(case)
    for fam in _FOCUS_FAMILIES:
        cases = by_family.get(fam, [])
        actions = {c["expected"] for c in cases}
        assert "drop" in actions, "family {} has no drop cases".format(fam)
        # Every focus family must have at least one keep OR a normalize case
        # so the family is not just a one-sided suppress test.
        assert ("keep" in actions) or ("normalize" in actions), fam


def test_report_serializes_to_json_round_trip():
    """Verify that report serializes to json round trip behaves the way the team expects."""
    report = run_fixture()
    payload = report.as_dict()
    serialized = json.dumps(payload)
    reloaded = json.loads(serialized)
    assert reloaded["fixture_id"] == report.fixture_id
    assert reloaded["total"] == report.total
    assert reloaded["passed"] == report.passed
    assert len(reloaded["verdicts"]) == report.total
    assert len(reloaded["families"]) == len(report.families)


def test_classifier_handles_unknown_entity_type_default_keep():
    """Verify that classifier handles unknown entity type default keep behaves the way the team expects."""
    action, canon, rule = classify("MYSTERY", "Anything")
    assert action == "keep"
    assert canon is None
    assert rule == "default_keep"


def test_classifier_part_default_keep_does_not_drop_specific_ids():
    # PART is a focus-adjacent family in the mining doc but the harness should
    # not drop structured part ids; lock that in.
    """Verify that classifier part default keep does not drop specific ids behaves the way the team expects."""
    for text in ("AS-5021", "OS-0004"):
        action, _canon, _rule = classify("PART", text)
        assert action == "keep", text


def test_harness_cli_main_returns_zero_on_full_pass(capsys):
    """Verify that harness cli main returns zero on full pass behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "100.0%" in out
    assert "Schema Pattern Regression Report" in out


def test_harness_cli_main_emits_json_when_requested(capsys):
    """Verify that harness cli main emits json when requested behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    rc = main(["--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["pass_rate"] == 1.0
    assert payload["failed"] == 0


# ---------------------------------------------------------------------------
# Tier3 negative fixture lock-in
# ---------------------------------------------------------------------------

_TIER3_FIXTURE_PATH = (
    DEFAULT_FIXTURE_PATH.parent / "fixture_tier3_negatives_2026_04_15.json"
)


def test_tier3_negative_fixture_exists():
    """Verify that tier3 negative fixture exists behaves the way the team expects."""
    assert _TIER3_FIXTURE_PATH.exists(), _TIER3_FIXTURE_PATH


def test_tier3_negative_fixture_full_pass():
    """Verify that tier3 negative fixture full pass behaves the way the team expects."""
    report = run_fixture(fixture_path=_TIER3_FIXTURE_PATH)
    assert report.failed == 0, [v.case_id for v in report.verdicts if not v.passed]
    assert report.passed == report.total
    assert report.fixture_id == "schema_pattern_regression_tier3_negatives_2026_04_15"
    # Every focus family must be exercised by a negative case, otherwise the
    # tier3 surface is incomplete.
    fam_names = {f.family for f in report.families}
    assert {
        "site_generic_placeholder_labels",
        "person_role_common_noun_leakage",
        "contact_numeric_junk_split",
        "date_header_label_leakage",
        "org_generic_bucket_and_case",
    } <= fam_names


# ---------------------------------------------------------------------------
# Multi-fixture CI smoke runner
# ---------------------------------------------------------------------------

def test_discover_fixtures_finds_tier1_and_tier3():
    """Verify that discover fixtures finds tier1 and tier3 behaves the way the team expects."""
    paths = discover_fixtures()
    names = {p.name for p in paths}
    assert "fixture_2026_04_15.json" in names
    assert "fixture_tier3_negatives_2026_04_15.json" in names


def test_run_all_fixtures_full_pass():
    """Verify that run all fixtures full pass behaves the way the team expects."""
    reports = run_all_fixtures()
    assert reports, "no fixtures discovered"
    assert all(r.failed == 0 for r in reports), [
        (r.fixture_id, r.failed) for r in reports if r.failed
    ]
    # Both tier1 and tier3 must be in the run set.
    fixture_ids = {r.fixture_id for r in reports}
    assert "schema_pattern_regression_2026_04_15" in fixture_ids
    assert "schema_pattern_regression_tier3_negatives_2026_04_15" in fixture_ids


def test_format_oneline_summary_pass_shape():
    """Verify that format oneline summary pass shape behaves the way the team expects."""
    reports = run_all_fixtures()
    line = format_oneline_summary(reports)
    assert line.startswith("schema_pattern_regression: PASS")
    assert "fixtures={}".format(len(reports)) in line
    assert "failed=0" in line


def test_format_oneline_summary_empty_input():
    """Verify that format oneline summary empty input behaves the way the team expects."""
    line = format_oneline_summary([])
    assert "no fixtures discovered" in line


def test_format_oneline_summary_fail_shape(tmp_path):
    # Build a tiny fixture that forces a failure and compose the line.
    """Verify that format oneline summary fail shape behaves the way the team expects."""
    bad = {
        "fixture_id": "bad_oneline_test",
        "frozen_at": "2026-04-15",
        "store_snapshot": {},
        "families": ["site_generic_placeholder_labels"],
        "cases": [
            {
                "id": "force_fail",
                "family": "site_generic_placeholder_labels",
                "text": "Peterson AFB",
                "entity_type": "SITE",
                "expected": "drop",
            }
        ],
        "normalization_clusters": [],
    }
    bad_path = tmp_path / "fixture_bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    reports = run_all_fixtures(directory=tmp_path)
    line = format_oneline_summary(reports)
    assert line.startswith("schema_pattern_regression: FAIL")
    assert "failed=1" in line


def test_harness_cli_main_all_oneline(capsys):
    """Verify that harness cli main all oneline behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    rc = main(["--all", "--oneline"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.startswith("schema_pattern_regression: PASS")
    assert "fixtures=" in out


def test_harness_cli_main_all_json(capsys):
    """Verify that harness cli main all json behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    rc = main(["--all", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert "summary" in payload
    assert "reports" in payload
    assert payload["summary"].startswith("schema_pattern_regression: PASS")
    assert len(payload["reports"]) >= 2


def test_harness_cli_main_all_directory_override(tmp_path, capsys):
    """Verify that harness cli main all directory override behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    # Empty dir -> no fixtures discovered, exit 0 (vacuously true), oneline says so.
    rc = main(["--all", "--oneline", "--directory", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no fixtures discovered" in out


def test_tier3_negative_fixture_includes_both_keep_and_drop():
    """Verify that tier3 negative fixture includes both keep and drop behaves the way the team expects."""
    fixture = load_fixture(_TIER3_FIXTURE_PATH)
    actions = {c["expected"] for c in fixture["cases"]}
    # Negative tier must probe both directions: rules that should NOT fire
    # AND rules that SHOULD fire on near-miss inputs.
    assert "keep" in actions
    assert "drop" in actions


# ---------------------------------------------------------------------------
# Fixture validator
# ---------------------------------------------------------------------------

def test_validate_fixture_passes_on_frozen_tier1():
    """Verify that validate fixture passes on frozen tier1 behaves the way the team expects."""
    assert validate_fixture(load_fixture()) == []


def test_validate_fixture_passes_on_tier3_negatives():
    """Verify that validate fixture passes on tier3 negatives behaves the way the team expects."""
    assert validate_fixture(load_fixture(_TIER3_FIXTURE_PATH)) == []


def test_validate_fixture_rejects_non_dict():
    """Verify that validate fixture rejects non dict behaves the way the team expects."""
    errs = validate_fixture(["not", "a", "dict"])
    assert errs and "JSON object" in errs[0]


def test_validate_fixture_flags_missing_fixture_id():
    """Verify that validate fixture flags missing fixture id behaves the way the team expects."""
    errs = validate_fixture({"cases": []})
    assert any("fixture_id" in e for e in errs)


def test_validate_fixture_flags_missing_cases():
    """Verify that validate fixture flags missing cases behaves the way the team expects."""
    errs = validate_fixture({"fixture_id": "x"})
    assert any("cases" in e for e in errs)


def test_validate_fixture_flags_cases_not_a_list():
    """Verify that validate fixture flags cases not a list behaves the way the team expects."""
    errs = validate_fixture({"fixture_id": "x", "cases": "nope"})
    assert any("cases must be a list" in e for e in errs)


def test_validate_fixture_flags_empty_cases():
    """Verify that validate fixture flags empty cases behaves the way the team expects."""
    errs = validate_fixture({"fixture_id": "x", "cases": []})
    assert any("empty" in e for e in errs)


def test_validate_fixture_flags_duplicate_ids():
    """Verify that validate fixture flags duplicate ids behaves the way the team expects."""
    fixture = {
        "fixture_id": "x",
        "cases": [
            {"id": "dup", "text": "a", "entity_type": "SITE", "expected": "keep"},
            {"id": "dup", "text": "b", "entity_type": "SITE", "expected": "keep"},
        ],
    }
    errs = validate_fixture(fixture)
    assert any("duplicate id: dup" in e for e in errs)


def test_validate_fixture_flags_invalid_expected_value():
    """Verify that validate fixture flags invalid expected value behaves the way the team expects."""
    fixture = {
        "fixture_id": "x",
        "cases": [
            {"id": "a", "text": "t", "entity_type": "SITE", "expected": "maybe"},
        ],
    }
    errs = validate_fixture(fixture)
    assert any("expected must be one of" in e for e in errs)


def test_validate_fixture_flags_normalize_missing_canonical():
    """Verify that validate fixture flags normalize missing canonical behaves the way the team expects."""
    fixture = {
        "fixture_id": "x",
        "cases": [
            {"id": "a", "text": "t", "entity_type": "ORG", "expected": "normalize"},
        ],
    }
    errs = validate_fixture(fixture)
    assert any("normalize case missing canonical" in e for e in errs)


def test_validate_fixture_flags_missing_required_case_keys():
    """Verify that validate fixture flags missing required case keys behaves the way the team expects."""
    fixture = {
        "fixture_id": "x",
        "cases": [{"id": "a"}],
    }
    errs = validate_fixture(fixture)
    # Must complain about each of: text, entity_type, expected
    joined = "\n".join(errs)
    for k in ("text", "entity_type", "expected"):
        assert "missing required key: {}".format(k) in joined, joined


def test_validate_fixture_flags_non_dict_case():
    """Verify that validate fixture flags non dict case behaves the way the team expects."""
    fixture = {"fixture_id": "x", "cases": ["nope"]}
    errs = validate_fixture(fixture)
    assert any("must be a JSON object" in e for e in errs)


def test_harness_cli_main_validate_passes(capsys):
    """Verify that harness cli main validate passes behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    rc = main(["--validate", str(DEFAULT_FIXTURE_PATH)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "validate: OK" in out


def test_harness_cli_main_validate_fails(tmp_path, capsys):
    """Verify that harness cli main validate fails behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    bad_path = tmp_path / "fixture_bad.json"
    bad_path.write_text(json.dumps({"fixture_id": "x"}), encoding="utf-8")
    rc = main(["--validate", str(bad_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "validate:" in out
    assert "cases" in out  # error about missing cases key


def test_harness_cli_main_validate_handles_missing_file(tmp_path, capsys):
    """Verify that harness cli main validate handles missing file behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    missing = tmp_path / "nope.json"
    rc = main(["--validate", str(missing)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "failed to load fixture" in out


def test_harness_cli_main_returns_one_on_failure(tmp_path, capsys):
    """Verify that harness cli main returns one on failure behaves the way the team expects."""
    from src.regression.schema_pattern.harness import main

    # Build a tiny fixture with one impossible expectation to force a failure.
    bad = {
        "fixture_id": "bad_test_fixture",
        "frozen_at": "2026-04-15",
        "store_snapshot": {},
        "families": ["site_generic_placeholder_labels"],
        "cases": [
            {
                "id": "force_fail",
                "family": "site_generic_placeholder_labels",
                "text": "Peterson AFB",
                "entity_type": "SITE",
                "expected": "drop",
            }
        ],
        "normalization_clusters": [],
    }
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")

    rc = main(["--fixture", str(bad_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out or "force_fail" in out

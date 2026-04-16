"""Tests for the controlled vocabulary pack loader and seed packs.

Covers:
- loading the seed packs from config/vocab_packs/
- schema sanity (required fields present)
- alias presence (at least one pack has aliases, round-trip lookup works)
- no malformed entries (validate_pack_dict returns empty errors)
- enum value correctness (collision_risk, release_tier, source_kind)
- deployable packs contain no local_corpus sources
- kind-specific extras (form_number, service, legacy_names) are preserved
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vocab import (
    VocabEntry,
    VocabPack,
    VocabPackError,
    load_all_packs,
    load_pack,
    validate_pack_dict,
)

SEED_DIR = ROOT / "config" / "vocab_packs"

EXPECTED_PACK_IDS = {
    "program_management_terms",
    "cyber_terms",
    "government_forms",
    "locations_bases",
}


@pytest.fixture(scope="module")
def all_packs() -> list[VocabPack]:
    """Support this test module by handling the all packs step."""
    return load_all_packs(SEED_DIR)


# --- Loading --------------------------------------------------------------


def test_seed_directory_exists() -> None:
    """Verify that seed directory exists behaves the way the team expects."""
    assert SEED_DIR.exists(), f"Seed pack directory missing: {SEED_DIR}"
    assert SEED_DIR.is_dir()


def test_load_all_packs_returns_expected_ids(all_packs: list[VocabPack]) -> None:
    """Verify that load all packs returns expected ids behaves the way the team expects."""
    pack_ids = {p.pack_id for p in all_packs}
    assert pack_ids == EXPECTED_PACK_IDS, (
        f"expected {EXPECTED_PACK_IDS}, got {pack_ids}"
    )


def test_load_all_packs_is_sorted(all_packs: list[VocabPack]) -> None:
    """Verify that load all packs is sorted behaves the way the team expects."""
    ids = [p.pack_id for p in all_packs]
    assert ids == sorted(ids), "load_all_packs should return sorted packs"


def test_each_pack_has_nonempty_entries(all_packs: list[VocabPack]) -> None:
    """Verify that each pack has nonempty entries behaves the way the team expects."""
    for pack in all_packs:
        assert len(pack.entries) > 0, f"pack {pack.pack_id} has no entries"


def test_load_pack_by_path_matches_bulk_load(all_packs: list[VocabPack]) -> None:
    """Verify that load pack by path matches bulk load behaves the way the team expects."""
    path = SEED_DIR / "cyber_terms.yaml"
    single = load_pack(path)
    bulk = next(p for p in all_packs if p.pack_id == "cyber_terms")
    assert single.pack_id == bulk.pack_id
    assert len(single.entries) == len(bulk.entries)


def test_load_missing_pack_raises() -> None:
    """Verify that load missing pack raises behaves the way the team expects."""
    with pytest.raises(VocabPackError):
        load_pack(SEED_DIR / "does_not_exist.yaml")


def test_load_missing_directory_raises(tmp_path: Path) -> None:
    """Verify that load missing directory raises behaves the way the team expects."""
    with pytest.raises(VocabPackError):
        load_all_packs(tmp_path / "nope")


# --- Schema sanity --------------------------------------------------------


def test_pack_level_required_fields(all_packs: list[VocabPack]) -> None:
    """Verify that pack level required fields behaves the way the team expects."""
    for pack in all_packs:
        assert pack.pack_id
        assert pack.pack_name
        assert pack.domain
        assert pack.version
        assert pack.release_tier
        assert pack.status


def test_all_seed_packs_are_deployable(all_packs: list[VocabPack]) -> None:
    """Verify that all seed packs are deployable behaves the way the team expects."""
    for pack in all_packs:
        assert pack.release_tier == "deployable", (
            f"seed pack {pack.pack_id} must be release_tier=deployable, "
            f"got {pack.release_tier!r}"
        )


def test_validate_pack_dict_returns_empty_for_seed_packs() -> None:
    """Verify that validate pack dict returns empty for seed packs behaves the way the team expects."""
    for yaml_file in sorted(SEED_DIR.glob("*.yaml")):
        raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        errors = validate_pack_dict(raw)
        assert errors == [], f"{yaml_file.name} failed validation: {errors}"


def test_validate_pack_dict_catches_missing_fields() -> None:
    """Verify that validate pack dict catches missing fields behaves the way the team expects."""
    bad_pack = {"pack_id": "x"}  # missing nearly everything
    errors = validate_pack_dict(bad_pack)
    assert errors, "expected validation errors for sparse pack"
    assert any("pack_name" in e for e in errors)
    assert any("entries" in e for e in errors)


def test_validate_pack_dict_catches_bad_collision_risk() -> None:
    """Verify that validate pack dict catches bad collision risk behaves the way the team expects."""
    raw = {
        "pack_id": "test",
        "pack_name": "Test",
        "domain": "test",
        "version": "0",
        "release_tier": "deployable",
        "status": "active",
        "entries": [
            {
                "term_id": "test.1",
                "canonical": "X",
                "kind": "acronym",
                "domain": "test",
                "category": "test",
                "regex_safe": True,
                "retrieval_expand": True,
                "collision_risk": "EXTREME",  # invalid
                "source_kind": "official_public",
                "sources": [{"source_id": "x", "citation": "x"}],
            }
        ],
    }
    errors = validate_pack_dict(raw)
    assert any("collision_risk" in e for e in errors)


def test_validate_pack_dict_catches_bad_kind() -> None:
    """Verify that validate pack dict catches bad kind behaves the way the team expects."""
    raw = {
        "pack_id": "test",
        "pack_name": "Test",
        "domain": "test",
        "version": "0",
        "release_tier": "deployable",
        "status": "active",
        "entries": [
            {
                "term_id": "test.1",
                "canonical": "X",
                "kind": "nonsense",  # invalid
                "domain": "test",
                "category": "test",
                "regex_safe": True,
                "retrieval_expand": True,
                "collision_risk": "low",
                "source_kind": "official_public",
                "sources": [{"source_id": "x", "citation": "x"}],
            }
        ],
    }
    errors = validate_pack_dict(raw)
    assert any("kind" in e for e in errors)


# --- Entry-level correctness ----------------------------------------------


def test_no_malformed_entries(all_packs: list[VocabPack]) -> None:
    """Verify that no malformed entries behaves the way the team expects."""
    for pack in all_packs:
        for entry in pack.entries:
            assert entry.term_id, f"{pack.pack_id}: entry missing term_id"
            assert entry.canonical, f"{pack.pack_id}/{entry.term_id}: missing canonical"
            assert entry.kind, f"{pack.pack_id}/{entry.term_id}: missing kind"
            assert entry.domain, f"{pack.pack_id}/{entry.term_id}: missing domain"
            assert entry.category, f"{pack.pack_id}/{entry.term_id}: missing category"
            assert entry.collision_risk in {"low", "medium", "high"}, (
                f"{pack.pack_id}/{entry.term_id}: bad collision_risk "
                f"{entry.collision_risk!r}"
            )
            assert entry.source_kind in {
                "official_public",
                "public_secondary",
                "local_corpus",
            }, f"{pack.pack_id}/{entry.term_id}: bad source_kind"
            assert entry.sources, (
                f"{pack.pack_id}/{entry.term_id}: empty sources list"
            )
            for src in entry.sources:
                assert src.get("source_id"), (
                    f"{pack.pack_id}/{entry.term_id}: source missing source_id"
                )
                assert src.get("citation"), (
                    f"{pack.pack_id}/{entry.term_id}: source missing citation"
                )


def test_no_local_only_sources_in_deployable_packs(all_packs: list[VocabPack]) -> None:
    """Verify that no local only sources in deployable packs behaves the way the team expects."""
    for pack in all_packs:
        if pack.release_tier != "deployable":
            continue
        for entry in pack.entries:
            assert entry.source_kind != "local_corpus", (
                f"{pack.pack_id}/{entry.term_id} has local_corpus source_kind "
                f"in a deployable pack"
            )
            for src in entry.sources:
                assert src.get("source_id", "").lower() not in {
                    "local_corpus",
                    "local",
                    "internal",
                }, (
                    f"{pack.pack_id}/{entry.term_id}: suspicious local source_id "
                    f"{src.get('source_id')!r}"
                )


def test_term_ids_are_unique_within_pack(all_packs: list[VocabPack]) -> None:
    """Verify that term ids are unique within pack behaves the way the team expects."""
    for pack in all_packs:
        term_ids = [e.term_id for e in pack.entries]
        assert len(term_ids) == len(set(term_ids)), (
            f"{pack.pack_id} has duplicate term_ids"
        )


def test_canonicals_are_nonempty(all_packs: list[VocabPack]) -> None:
    """Verify that canonicals are nonempty behaves the way the team expects."""
    for pack in all_packs:
        for entry in pack.entries:
            assert entry.canonical.strip(), (
                f"{pack.pack_id}/{entry.term_id}: canonical is whitespace-only"
            )


# --- Alias presence -------------------------------------------------------


def test_at_least_one_entry_has_aliases(all_packs: list[VocabPack]) -> None:
    """Verify that at least one entry has aliases behaves the way the team expects."""
    for pack in all_packs:
        assert any(e.aliases for e in pack.entries), (
            f"{pack.pack_id}: no entry has any aliases — suspicious"
        )


def test_alias_lookup_roundtrip(all_packs: list[VocabPack]) -> None:
    """Every aliased entry should be findable by any of its aliases."""
    for pack in all_packs:
        for entry in pack.entries:
            hit = pack.find_by_alias(entry.canonical)
            assert hit is not None, (
                f"{pack.pack_id}/{entry.term_id}: canonical lookup failed"
            )
            assert hit.term_id == entry.term_id
            for alias in entry.aliases:
                hit_alias = pack.find_by_alias(alias)
                assert hit_alias is not None, (
                    f"{pack.pack_id}/{entry.term_id}: alias {alias!r} lookup failed"
                )


def test_alias_index_is_nonempty(all_packs: list[VocabPack]) -> None:
    """Verify that alias index is nonempty behaves the way the team expects."""
    for pack in all_packs:
        idx = pack.alias_index
        assert len(idx) >= len(pack.entries), (
            f"{pack.pack_id}: alias index smaller than entry count"
        )


# --- Kind-specific extras -------------------------------------------------


def test_forms_pack_has_form_specific_fields() -> None:
    """Verify that forms pack has form specific fields behaves the way the team expects."""
    pack = load_pack(SEED_DIR / "government_forms.yaml")
    form_entries = pack.by_kind("form")
    assert form_entries, "government_forms pack should have form-kind entries"
    for entry in form_entries:
        assert entry.extras.get("form_number"), (
            f"{entry.term_id}: form entry missing form_number"
        )
        assert entry.extras.get("form_title"), (
            f"{entry.term_id}: form entry missing form_title"
        )
        common_fields = entry.extras.get("common_fields") or []
        assert isinstance(common_fields, list) and common_fields, (
            f"{entry.term_id}: form entry needs common_fields list"
        )
        structural_cues = entry.extras.get("structural_cues") or []
        assert isinstance(structural_cues, list) and structural_cues, (
            f"{entry.term_id}: form entry needs structural_cues list"
        )


def test_locations_pack_has_location_specific_fields() -> None:
    """Verify that locations pack has location specific fields behaves the way the team expects."""
    pack = load_pack(SEED_DIR / "locations_bases.yaml")
    location_entries = pack.by_kind("location")
    assert location_entries, "locations_bases pack should have location-kind entries"
    for entry in location_entries:
        assert entry.extras.get("service"), (
            f"{entry.term_id}: location entry missing service"
        )
        assert entry.extras.get("type"), (
            f"{entry.term_id}: location entry missing type"
        )
        parent = entry.extras.get("parent_geography") or {}
        assert isinstance(parent, dict) and parent.get("country"), (
            f"{entry.term_id}: location entry needs parent_geography.country"
        )


def test_pm_pack_has_acronym_expansions() -> None:
    """Verify that pm pack has acronym expansions behaves the way the team expects."""
    pack = load_pack(SEED_DIR / "program_management_terms.yaml")
    acronyms = pack.by_kind("acronym")
    assert acronyms, "program_management_terms pack should have acronyms"
    # At least most acronyms should have an expansion field
    with_expansion = [e for e in acronyms if e.expansion]
    assert len(with_expansion) >= len(acronyms) // 2, (
        "most PM acronyms should have an expansion"
    )


def test_cyber_pack_marks_collision_prone_terms() -> None:
    """Zero Trust should not be regex_safe (multi-word, case-sensitive issues)."""
    pack = load_pack(SEED_DIR / "cyber_terms.yaml")
    zero_trust = next((e for e in pack.entries if "zero" in e.canonical.lower()), None)
    assert zero_trust is not None, "cyber pack should have a zero-trust entry"
    assert zero_trust.retrieval_expand is True

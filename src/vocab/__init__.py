"""Controlled vocabulary pack library.

Public API:
    VocabEntry, VocabPack, load_pack, load_all_packs, validate_pack_dict
    plus read-only reporting helpers
"""

from src.vocab.pack_loader import (
    VocabEntry,
    VocabPack,
    VocabPackError,
    load_all_packs,
    load_pack,
    validate_pack_dict,
)
from src.vocab.pack_reports import (  # noqa: F401
    LookupHit,
    ScanHit,
    build_vocab_report,
    build_cross_pack_alias_collisions,
    find_scan_hits,
    find_lookup_hits,
    format_vocab_report,
    summarize_pack,
)
from src.vocab.tagging import (  # noqa: F401
    AmbiguousAliasWarning,
    build_tagging_result,
    format_tagging_result,
)

__all__ = [
    "VocabEntry",
    "VocabPack",
    "VocabPackError",
    "load_pack",
    "load_all_packs",
    "validate_pack_dict",
    "LookupHit",
    "ScanHit",
    "build_vocab_report",
    "build_cross_pack_alias_collisions",
    "find_scan_hits",
    "find_lookup_hits",
    "format_vocab_report",
    "summarize_pack",
    "AmbiguousAliasWarning",
    "build_tagging_result",
    "format_tagging_result",
]

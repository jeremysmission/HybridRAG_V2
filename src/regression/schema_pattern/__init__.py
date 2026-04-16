"""Schema-pattern regression package for replaying structured extraction cases against saved fixtures."""
from .harness import (
    Case,
    Verdict,
    Report,
    classify,
    load_fixture,
    run_fixture,
    discover_fixtures,
    run_all_fixtures,
    format_oneline_summary,
    validate_fixture,
    DEFAULT_FIXTURE_PATH,
)

__all__ = [
    "Case",
    "Verdict",
    "Report",
    "classify",
    "load_fixture",
    "run_fixture",
    "discover_fixtures",
    "run_all_fixtures",
    "format_oneline_summary",
    "validate_fixture",
    "DEFAULT_FIXTURE_PATH",
]

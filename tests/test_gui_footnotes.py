"""Isolated tests for query panel footnote numbering logic.

Validates that internal chunk numbers (e.g. [Source 14: ...]) are remapped
to sequential user-facing display numbers ([1], [2], [3]) by order of
first appearance, with repeated citations reusing the same number.
"""

import pytest
import tkinter as tk

from src.gui.panels import query_panel as query_panel_module
from src.gui.panels.query_panel import QueryPanel


def _resolve(explicit, cited, filenames):
    """Standalone copy of QueryPanel._resolve_source_index for testing."""
    cited_name = cited.strip().lower()
    cited_base = cited_name.split(",")[0].strip()
    if explicit:
        idx = int(explicit) - 1
        if 0 <= idx < len(filenames):
            return idx
    for i, sname in enumerate(filenames):
        if cited_base in sname or sname in cited_base:
            return i
    return -(hash(cited_name) % 10000) - 1


def _build_display_map(answer, filenames):
    """Simulate the two-pass footnote mapping from query_panel.py."""
    import re
    pattern = re.compile(
        r'\[Source(?:\s+(\d+))?:\s*([^\]]+)\]', re.IGNORECASE)
    display_map = {}
    next_num = 1
    for match in pattern.finditer(answer):
        idx = _resolve(match.group(1), match.group(2), filenames)
        if idx not in display_map:
            display_map[idx] = next_num
            next_num += 1
    return display_map


class TestFootnoteSequentialNumbering:

    def test_high_numbers_remapped_to_sequential(self):
        answer = (
            "According to [Source 14: report.pdf], the system is operational. "
            "See also [Source 7: manual.docx] for details."
        )
        filenames = ["report.pdf", "manual.docx"]
        # Source 14 resolves to index 13 which is out of range (only 2 sources).
        # Falls back to fuzzy match: "report.pdf" -> index 0
        # "manual.docx" -> index 1
        dm = _build_display_map(answer, filenames)
        assert dm[0] == 1, "First cited source should display as [1]"
        assert dm[1] == 2, "Second cited source should display as [2]"

    def test_repeated_citation_reuses_number(self):
        answer = (
            "[Source 1: alpha.pdf] says X. "
            "[Source 2: beta.pdf] says Y. "
            "[Source 1: alpha.pdf] confirms X."
        )
        filenames = ["alpha.pdf", "beta.pdf"]
        dm = _build_display_map(answer, filenames)
        assert dm[0] == 1
        assert dm[1] == 2
        assert len(dm) == 2, "Repeated citation should not create a new entry"

    def test_first_appearance_order(self):
        answer = (
            "[Source 3: charlie.pdf] first, "
            "[Source 1: alpha.pdf] second, "
            "[Source 2: beta.pdf] third."
        )
        filenames = ["alpha.pdf", "beta.pdf", "charlie.pdf"]
        dm = _build_display_map(answer, filenames)
        # charlie (idx 2) appears first -> display 1
        # alpha (idx 0) appears second -> display 2
        # beta (idx 1) appears third -> display 3
        assert dm[2] == 1
        assert dm[0] == 2
        assert dm[1] == 3

    def test_no_explicit_number_fuzzy_match(self):
        answer = "Per [Source: deployment_guide.pdf], the steps are..."
        filenames = ["deployment_guide.pdf", "other.txt"]
        dm = _build_display_map(answer, filenames)
        assert dm[0] == 1

    def test_citation_with_section_suffix(self):
        answer = "[Source: report.pdf, Section 3.2] describes the process."
        filenames = ["report.pdf"]
        dm = _build_display_map(answer, filenames)
        assert dm[0] == 1

    def test_unresolvable_citation_gets_unique_number(self):
        answer = (
            "[Source: known.pdf] is fine. "
            "[Source: mystery.pdf] is unknown."
        )
        filenames = ["known.pdf"]
        dm = _build_display_map(answer, filenames)
        assert dm[0] == 1
        resolved_keys = [k for k in dm if k >= 0]
        unresolved_keys = [k for k in dm if k < 0]
        assert len(resolved_keys) == 1
        assert len(unresolved_keys) == 1
        assert dm[unresolved_keys[0]] == 2

    def test_empty_answer_no_citations(self):
        dm = _build_display_map("No sources cited here.", ["a.pdf"])
        assert dm == {}

    def test_explicit_number_in_range(self):
        answer = "[Source 2: beta.pdf] has the data."
        filenames = ["alpha.pdf", "beta.pdf", "charlie.pdf"]
        dm = _build_display_map(answer, filenames)
        # Source 2 -> index 1 (beta.pdf) -> display 1 (first appearance)
        assert dm[1] == 1

    def test_mixed_explicit_and_fuzzy(self):
        answer = (
            "[Source 1: alpha.pdf] intro. "
            "[Source: charlie.pdf] detail."
        )
        filenames = ["alpha.pdf", "beta.pdf", "charlie.pdf"]
        dm = _build_display_map(answer, filenames)
        assert dm[0] == 1  # alpha -> display 1
        assert dm[2] == 2  # charlie -> display 2


class TestResolveSourceIndex:

    def test_explicit_in_range(self):
        assert _resolve("2", "beta.pdf", ["a.pdf", "beta.pdf"]) == 1

    def test_explicit_out_of_range_falls_to_fuzzy(self):
        idx = _resolve("99", "beta.pdf", ["alpha.pdf", "beta.pdf"])
        assert idx == 1  # fuzzy match on "beta.pdf"

    def test_no_explicit_fuzzy_match(self):
        assert _resolve(None, "report.pdf", ["report.pdf"]) == 0

    def test_no_match_returns_negative(self):
        idx = _resolve(None, "nonexistent.pdf", ["a.pdf", "b.pdf"])
        assert idx < 0

    def test_partial_filename_match(self):
        idx = _resolve(None, "guide", ["deployment_guide.pdf", "other.txt"])
        assert idx == 0


class _FakeWidget:
    def __init__(self, exists=True):
        self.exists = exists
        self.config_calls = []

    def winfo_exists(self):
        return 1 if self.exists else 0

    def config(self, **kwargs):
        self.config_calls.append(kwargs)


class _FakeVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class _ImmediateThread:
    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        if self._target:
            self._target()


class TestQueryPanelIntegrationSafety:

    def test_restore_source_card_style_ignores_destroyed_widget(self):
        panel = object.__new__(QueryPanel)
        widget = _FakeWidget(exists=False)

        QueryPanel._restore_source_card_style(panel, widget, "#333333")

        assert widget.config_calls == []

    def test_auto_detect_endpoint_uses_safe_after_from_probe_thread(self, monkeypatch):
        scheduled = []
        panel = object.__new__(QueryPanel)
        panel._model = type(
            "Model", (), {
                "llm_available": True,
                "_llm_client": type("Client", (), {"_provider": "openai"})(),
            }
        )()
        panel._endpoint_var = _FakeVar()
        panel._endpoint_status = _FakeWidget(exists=True)
        panel._endpoint_detect_start = 0.0
        panel._endpoint_detect_timeout = 60
        panel.after = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("background probe should not call self.after directly")
        )

        monkeypatch.setattr(
            query_panel_module,
            "safe_after",
            lambda widget, ms, fn, *args: scheduled.append(
                {"widget": widget, "ms": ms, "fn": fn, "args": args}
            ),
        )
        monkeypatch.setattr(query_panel_module.threading, "Thread", _ImmediateThread)

        QueryPanel._auto_detect_endpoint(panel)

        assert len(scheduled) == 1
        assert scheduled[0]["widget"] is panel
        assert scheduled[0]["ms"] == 0
        assert scheduled[0]["fn"].__name__ == "_update"

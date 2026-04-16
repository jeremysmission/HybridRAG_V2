"""
Lane 9.2 targeted GUI evidence capture for HybridRAG V2.

This is not a general GUI harness. It captures code-driven evidence for:
  - launch_gui resolving config/config.yaml
  - simplified Query / Entities / Settings surface
  - read-only Settings panel contract and runtime count refresh
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from unittest import mock

import tkinter as tk

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeCountStore:
    """Small helper object used to keep tool state or expected values organized."""
    def __init__(self, value: int):
        self.value = value

    def count(self) -> int:
        return self.value

    def count_entities(self) -> int:
        return self.value


def parse_args() -> argparse.Namespace:
    """Collect command-line options so the tool knows what evidence to capture."""
    parser = argparse.ArgumentParser(description="Capture targeted Lane 9.2 GUI evidence.")
    parser.add_argument("--visible", action="store_true", help="Show the Tk window instead of withdrawing it.")
    parser.add_argument("--output-dir", default="", help="Optional artifact directory.")
    return parser.parse_args()


def timestamp_slug() -> str:
    """Create a timestamp string so output files are easy to sort and trace."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_output_dir(path_arg: str) -> Path:
    """Create or resolve the output location this tool will write to."""
    if path_arg:
        out = Path(path_arg)
    else:
        out = ROOT / "docs" / "evidence" / f"lane9_2_gui_{timestamp_slug()}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def widget_text(widget: tk.Misc) -> str:
    """Inspect the GUI surface and return data that a reviewer can read later."""
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def collect_snapshot_lines(widget: tk.Misc, depth: int = 0) -> list[str]:
    """Gather the evidence this tool needs to save for later review."""
    line = f"{'  ' * depth}{widget.winfo_class()}"
    text = widget_text(widget)
    if text:
        line += f" text={text!r}"
    try:
        state = str(widget.cget("state"))
        if state:
            line += f" state={state!r}"
    except Exception:
        pass
    lines = [line]
    for child in widget.winfo_children():
        lines.extend(collect_snapshot_lines(child, depth + 1))
    return lines


def write_snapshot(path: Path, title: str, widget: tk.Misc, extra: dict | None = None) -> None:
    """Write the captured evidence to disk in a reusable form."""
    lines = [title, "=" * len(title), ""]
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {value}")
        lines.append("")
    lines.extend(collect_snapshot_lines(widget))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def walk_widgets(widget: tk.Misc):
    """Inspect the GUI surface and return data that a reviewer can read later."""
    yield widget
    for child in widget.winfo_children():
        yield from walk_widgets(child)


def visible_texts(widget: tk.Misc) -> list[str]:
    """Inspect the GUI surface and return data that a reviewer can read later."""
    return [text for w in walk_widgets(widget) if (text := widget_text(w))]


def fail_record(name: str, message: str) -> dict:
    """Build a consistent failure record so problems are easier to diagnose."""
    return {"name": name, "passed": False, "details": message}


def capture_launch_gui_check() -> dict:
    """Run one targeted capture scenario and return the resulting evidence."""
    import src.gui.launch_gui as launch_gui
    from src.config.schema import load_config as real_load_config

    captured: dict[str, str] = {"path": ""}

    def wrapped_load_config(path):
        captured["path"] = str(path)
        return real_load_config(path)

    class FakeApp:
        def __init__(self, model=None, config=None):
            self.model = model
            self.config = config

        def set_model(self, model):
            self.model = model

        def mainloop(self):
            return None

    with mock.patch("src.config.schema.load_config", side_effect=wrapped_load_config), \
         mock.patch("src.gui.app.HybridRAGApp", FakeApp), \
         mock.patch.object(threading.Thread, "start", lambda self: None):
        launch_gui.main()

    expected = str(ROOT / "config" / "config.yaml")
    return {
        "name": "launch_gui_config_path",
        "passed": captured["path"] == expected,
        "details": {
            "captured_path": captured["path"],
            "expected_path": expected,
        },
    }


def capture_gui_checks(output_dir: Path, visible: bool) -> tuple[list[dict], list[str]]:
    """Run one targeted capture scenario and return the resulting evidence."""
    from src.config.schema import load_config
    from src.gui.app import HybridRAGApp
    from src.gui.model import GUIModel
    from src.gui.panels.settings_panel import SettingsPanel

    config = load_config(ROOT / "config" / "config.yaml")
    model = GUIModel(
        lance_store=FakeCountStore(12345),
        entity_store=FakeCountStore(678),
        relationship_store=FakeCountStore(90),
        config=config,
    )
    app = HybridRAGApp(model=model, config=config)
    if not visible:
        app.withdraw()
    app.update_idletasks()
    app.update()

    checks: list[dict] = []
    evidence_paths: list[str] = []

    nav_labels = [lbl.cget("text") for lbl in app.nav_bar._tab_labels.values()]
    checks.append({
        "name": "simplified_nav_surface",
        "passed": nav_labels == ["Query", "Entities", "Settings"],
        "details": {"nav_labels": nav_labels, "current_view": app._current_view},
    })

    app.show_view("settings")
    app.update_idletasks()
    app.update()
    panel = app._views["settings"]

    before_path = output_dir / "settings_before_refresh.txt"
    write_snapshot(
        before_path,
        "Lane 9.2 Settings Snapshot (Before Refresh)",
        panel,
        extra={"selected_view": app._current_view, "nav_labels": ", ".join(nav_labels)},
    )
    evidence_paths.append(str(before_path))

    interactive = []
    for widget in walk_widgets(panel):
        if isinstance(widget, (tk.Entry, tk.Text, tk.Spinbox, tk.Checkbutton, tk.Radiobutton)):
            interactive.append(type(widget).__name__)
    checks.append({
        "name": "settings_panel_read_only",
        "passed": not interactive,
        "details": {
            "interactive_widgets_found": interactive,
            "refresh_button_text": panel._refresh_btn.cget("text"),
        },
    })

    rendered_texts = visible_texts(panel)
    expected_runtime_tokens = [
        "Refresh Counts",
        config.llm.model,
        config.paths.lance_db,
        config.paths.embedengine_output,
    ]
    missing_runtime = [token for token in expected_runtime_tokens if token not in rendered_texts]
    checks.append({
        "name": "settings_panel_runtime_config_display",
        "passed": not missing_runtime,
        "details": {
            "missing_tokens": missing_runtime,
            "checked_tokens": expected_runtime_tokens,
            "rendered_texts": rendered_texts,
        },
    })

    doc_text = inspect.getdoc(SettingsPanel) or ""
    wording = "config/config.yaml and restarting."
    checks.append({
        "name": "settings_guidance_source_contract",
        "passed": wording in doc_text,
        "details": {
            "required_phrase": wording,
            "docstring_present": bool(doc_text),
            "rendered_guidance_present": wording in rendered_texts,
            "scope_note": (
                "Source-level check only. This validates the SettingsPanel "
                "implementation guidance contract, not operator-visible widget text."
            ),
        },
    })

    before_counts = panel._counts_label.cget("text")
    panel._refresh_btn.invoke()
    app.update_idletasks()
    app.update()
    after_counts = panel._counts_label.cget("text")
    after_path = output_dir / "settings_after_refresh.txt"
    write_snapshot(
        after_path,
        "Lane 9.2 Settings Snapshot (After Refresh)",
        panel,
        extra={"counts_before": before_counts, "counts_after": after_counts},
    )
    evidence_paths.append(str(after_path))
    checks.append({
        "name": "refresh_counts_runtime_status",
        "passed": after_counts == "Chunks: 12,345 | Entities: 678 | Rels: 90",
        "details": {"before": before_counts, "after": after_counts},
    })

    app.destroy()
    return checks, evidence_paths


def main() -> int:
    """Parse command-line inputs and run this tool end to end."""
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)
    evidence = {
        "evidence_version": "1.0",
        "lane": "9.2",
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(ROOT),
        "scope_note": (
            "Targeted evidence for Lane 9.2 scope only. This does not replace the "
            "required Tier D non-author human button smash."
        ),
        "mode": "visible" if args.visible else "headless-withdrawn",
        "checks": [],
        "artifacts": [],
    }

    try:
        evidence["checks"].append(capture_launch_gui_check())
        gui_checks, artifacts = capture_gui_checks(output_dir, args.visible)
        evidence["checks"].extend(gui_checks)
        evidence["artifacts"].extend(artifacts)
    except Exception as exc:
        evidence["checks"].append(fail_record("capture_runtime", repr(exc)))

    passed = all(check.get("passed") for check in evidence["checks"])
    evidence["verdict"] = "PASS" if passed else "FAIL"
    json_path = output_dir / f"gui_evidence_{timestamp_slug()}.json"
    json_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json_path)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

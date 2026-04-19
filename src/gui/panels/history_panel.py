"""Query history panel — shows recent query sessions with answers and sources."""

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_SMALL, FONT_MONO

SESSION_LOG_DIR = Path("data/query_sessions")


class HistoryPanel(tk.LabelFrame):
    """Displays recent query sessions from the daily JSONL log.

    Operators can click a session to view the full answer and sources
    without rerunning the query.
    """

    def __init__(self, parent, model):
        t = current_theme()
        super().__init__(
            parent, text="Query History", padx=16, pady=16,
            bg=t["panel_bg"], fg=t["accent"], font=FONT_BOLD,
        )
        self._model = model
        self._sessions: list[dict] = []
        self._build_widgets(t)
        self.after(500, self._load_sessions)

    def _build_widgets(self, t):
        # Refresh button
        top_row = tk.Frame(self, bg=t["panel_bg"])
        top_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            top_row, text="Recent queries (today):",
            bg=t["panel_bg"], fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        tk.Button(
            top_row, text="Refresh", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            command=self._load_sessions, cursor="hand2",
        ).pack(side=tk.RIGHT)

        # Session list (scrollable)
        list_frame = tk.Frame(self, bg=t["panel_bg"])
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self._session_listbox = tk.Listbox(
            list_frame, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            selectbackground=t["accent"], selectforeground=t["accent_fg"],
            relief=tk.FLAT, bd=1, yscrollcommand=scrollbar.set,
            activestyle="none",
        )
        scrollbar.config(command=self._session_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._session_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._session_listbox.bind("<<ListboxSelect>>", self._on_select)

        # Detail area
        detail_frame = tk.Frame(self, bg=t["panel_bg"])
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self._detail_text = tk.Text(
            detail_frame, height=12, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
        )
        detail_scroll = tk.Scrollbar(detail_frame, orient=tk.VERTICAL,
                                      command=self._detail_text.yview)
        self._detail_text.config(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Metrics line
        self._metrics_label = tk.Label(
            self, text="", anchor=tk.W, fg=t["gray"],
            bg=t["panel_bg"], font=FONT_MONO,
        )
        self._metrics_label.pack(fill=tk.X, pady=(4, 0))

    def _load_sessions(self):
        """Load today's sessions from the JSONL log."""
        self._sessions.clear()
        self._session_listbox.delete(0, tk.END)

        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = SESSION_LOG_DIR / f"sessions_{date_str}.jsonl"
        if not log_file.exists():
            self._session_listbox.insert(tk.END, "(no queries today)")
            return

        try:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        session = json.loads(line)
                        self._sessions.append(session)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            self._session_listbox.insert(tk.END, "(error reading log)")
            return

        # Display in reverse chronological order (newest first)
        for i, session in enumerate(reversed(self._sessions)):
            ts = session.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                time_str = dt.strftime("%H:%M:%S")
            except (ValueError, TypeError):
                time_str = "??:??:??"
            question = session.get("question", "(no question)")[:60]
            path = session.get("query_path", "")
            feedback = session.get("feedback", "")
            fb_icon = {"helpful": "\u2714", "not_helpful": "\u2718",
                       "wrong_answer": "\u26A0", "bad_sources": "\u2757"}.get(
                feedback, "")
            entry = f"[{time_str}] [{path}] {fb_icon} {question}"
            self._session_listbox.insert(tk.END, entry)

    def _on_select(self, event=None):
        """Display selected session details."""
        selection = self._session_listbox.curselection()
        if not selection:
            return
        # Index is reversed (newest first)
        idx = len(self._sessions) - 1 - selection[0]
        if idx < 0 or idx >= len(self._sessions):
            return
        session = self._sessions[idx]

        t = current_theme()
        question = session.get("question", "")
        answer = session.get("answer", "(no answer)")
        sources = session.get("sources", [])
        feedback = session.get("feedback", "none")
        latency = session.get("latency_ms", 0)
        chunks = session.get("chunks_used", 0)
        path = session.get("query_path", "")
        confidence = session.get("confidence", "")

        detail = (
            f"Question: {question}\n\n"
            f"Answer:\n{answer}\n\n"
            f"Sources:\n" + "\n".join(f"  - {s}" for s in sources) + "\n\n"
            f"Feedback: {feedback}"
        )

        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert("1.0", detail)
        self._detail_text.config(state=tk.DISABLED)

        self._metrics_label.config(
            text=f"Path: {path}  |  Confidence: {confidence}  |  "
                 f"Latency: {latency}ms  |  Chunks: {chunks}",
            fg=t["fg"],
        )

    def apply_theme(self, t):
        """Re-apply theme colors."""
        self.configure(bg=t["panel_bg"], fg=t["accent"])
        self._session_listbox.configure(
            bg=t["input_bg"], fg=t["input_fg"],
            selectbackground=t["accent"],
        )
        self._detail_text.configure(
            bg=t["input_bg"], fg=t["input_fg"],
        )
        self._metrics_label.configure(bg=t["panel_bg"])

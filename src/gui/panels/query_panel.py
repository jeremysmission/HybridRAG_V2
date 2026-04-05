# ============================================================================
# HybridRAG V2 -- Query Panel (src/gui/panels/query_panel.py)
# ============================================================================
# Main search interface: type a question, get an answer.
# V2 additions over V1:
#   - Query path badge (colored: SEMANTIC/ENTITY/AGGREGATE/TABULAR/COMPLEX)
#   - Graduated confidence indicator (green=HIGH, yellow=PARTIAL, red=NOT_FOUND)
#   - Streaming token display (background thread + safe_after + token queue)
#   - Source citations expandable section
#   - Stop button for cancellation
#   - Uses GUIModel.query() -- not direct pipeline access
# ============================================================================

import tkinter as tk
from tkinter import ttk
import threading
import time
import logging
import queue

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_SMALL, FONT_MONO
from src.gui.helpers.safe_after import safe_after

logger = logging.getLogger(__name__)

# Query path badge colors (looked up from theme at render time)
_PATH_COLORS = {
    "SEMANTIC": "accent",
    "ENTITY": "green",
    "AGGREGATE": "orange",
    "TABULAR": "orange",
    "COMPLEX": "red",
}

# Confidence badge colors
_CONFIDENCE_COLORS = {
    "HIGH": "green",
    "PARTIAL": "orange",
    "NOT_FOUND": "red",
}


class QueryPanel(tk.LabelFrame):
    """Query input and answer display panel.

    Shows question entry, Ask/Stop buttons, streaming answer area,
    query path badge, confidence indicator, and expandable sources.
    """

    def __init__(self, parent, model):
        """Create the query panel.

        Args:
            parent: Parent tk widget.
            model: GUIModel instance for dispatching queries.
        """
        t = current_theme()
        super().__init__(parent, text="Query", padx=16, pady=16,
                         bg=t["panel_bg"], fg=t["accent"],
                         font=FONT_BOLD)
        self._model = model
        self._streaming = False
        self._stream_start = 0.0
        self._elapsed_timer_id = None
        self._token_queue = queue.Queue()
        self._token_pump_id = None

        self._build_widgets(t)

        # Enable Ask button if pipeline is available
        self.after(200, self._check_ready)

    def _build_widgets(self, t):
        """Build all child widgets with theme colors."""

        # -- Row 0: Badge row (query path + confidence) --
        badge_row = tk.Frame(self, bg=t["panel_bg"])
        badge_row.pack(fill=tk.X, pady=(0, 8))

        self._path_badge = tk.Label(
            badge_row, text="", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["gray"], padx=8, pady=2,
        )
        self._path_badge.pack(side=tk.LEFT)

        self._confidence_badge = tk.Label(
            badge_row, text="", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["gray"], padx=8, pady=2,
        )
        self._confidence_badge.pack(side=tk.LEFT, padx=(8, 0))

        self._elapsed_label = tk.Label(
            badge_row, text="", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["gray"],
        )
        self._elapsed_label.pack(side=tk.RIGHT)

        # -- Row 1: Question + Ask + Stop --
        q_label = tk.Label(
            self, text="Question:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT, anchor=tk.W,
        )
        q_label.pack(fill=tk.X, pady=(0, 4))

        row_q = tk.Frame(self, bg=t["panel_bg"])
        row_q.pack(fill=tk.X, pady=(0, 6))

        self.question_entry = tk.Entry(
            row_q, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=2,
        )
        self.question_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.question_entry.insert(0, "Type your question here...")
        self.question_entry.bind("<FocusIn>", self._on_entry_focus)
        self.question_entry.bind("<Return>", self._on_ask)
        self.question_entry.bind("<Escape>", self._on_stop)

        self.ask_btn = tk.Button(
            row_q, text="Ask", command=self._on_ask, width=10,
            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            font=FONT_BOLD, relief=tk.FLAT, bd=0,
            padx=24, pady=8, state=tk.DISABLED,
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"],
        )
        self.ask_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.stop_btn = tk.Button(
            row_q, text="Stop", command=self._on_stop, width=10,
            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            font=FONT_BOLD, relief=tk.FLAT, bd=0,
            padx=24, pady=8, state=tk.DISABLED,
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"],
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        # -- Top-k selector --
        topk_row = tk.Frame(self, bg=t["panel_bg"])
        topk_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            topk_row, text="Top-K:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        self._topk_var = tk.IntVar(value=10)
        self._topk_spin = tk.Spinbox(
            topk_row, from_=1, to=50, textvariable=self._topk_var,
            width=5, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            buttonbackground=t["input_bg"], relief=tk.FLAT, bd=1,
        )
        self._topk_spin.pack(side=tk.LEFT, padx=(8, 0))

        # -- Network/status indicator --
        self._status_label = tk.Label(
            self, text="", fg=t["gray"], anchor=tk.W,
            bg=t["panel_bg"], font=FONT, justify=tk.LEFT,
        )
        self._status_label.pack(fill=tk.X)

        # -- Answer area (scrollable, selectable) --
        answer_frame = tk.Frame(self, bg=t["panel_bg"])
        answer_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        scrollbar = tk.Scrollbar(answer_frame, orient=tk.VERTICAL)
        self.answer_text = tk.Text(
            answer_frame, height=16, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=1,
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.answer_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.answer_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # -- Sources expandable section --
        self._sources_frame = tk.Frame(self, bg=t["panel_bg"])
        self._sources_frame.pack(fill=tk.X, pady=(8, 0))

        self._sources_toggle_btn = tk.Button(
            self._sources_frame, text="+ Sources (0)", font=FONT,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            command=self._toggle_sources, cursor="hand2",
            activebackground=t["panel_bg"], activeforeground=t["accent_hover"],
        )
        self._sources_toggle_btn.pack(anchor=tk.W)

        self._sources_detail = tk.Text(
            self._sources_frame, height=4, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._sources_expanded = False

        # -- Metrics line --
        self._metrics_label = tk.Label(
            self, text="", anchor=tk.W, fg=t["gray"],
            bg=t["panel_bg"], font=FONT_MONO, justify=tk.LEFT,
        )
        self._metrics_label.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Placeholder handling
    # ------------------------------------------------------------------

    def _on_entry_focus(self, event=None):
        """Clear placeholder text on first focus."""
        if self.question_entry.get() == "Type your question here...":
            self.question_entry.delete(0, tk.END)

    # ------------------------------------------------------------------
    # Ready check
    # ------------------------------------------------------------------

    def _check_ready(self):
        """Enable Ask button once the model pipeline is available."""
        t = current_theme()
        if self._model and self._model.pipeline is not None:
            self.ask_btn.config(
                state=tk.NORMAL,
                bg=t["accent"], fg=t["accent_fg"],
            )
        else:
            # Retry in 500ms
            self.after(500, self._check_ready)

    def set_ready(self, ready: bool):
        """Externally signal readiness (called after backend init)."""
        t = current_theme()
        if ready:
            self.ask_btn.config(
                state=tk.NORMAL,
                bg=t["accent"], fg=t["accent_fg"],
            )
        else:
            self.ask_btn.config(
                state=tk.DISABLED,
                bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            )

    # ------------------------------------------------------------------
    # Query lifecycle
    # ------------------------------------------------------------------

    def _on_ask(self, event=None):
        """Handle Ask button click or Enter key."""
        question = self.question_entry.get().strip()
        if not question or question == "Type your question here...":
            return
        if self._model is None or self._model.is_querying:
            return

        t = current_theme()
        top_k = self._topk_var.get()

        # Clear previous answer
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.config(state=tk.DISABLED)

        # Reset badges
        self._path_badge.config(text="", fg=t["gray"])
        self._confidence_badge.config(text="", fg=t["gray"])

        # Update UI state
        self.ask_btn.config(state=tk.DISABLED,
                            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"])
        self.stop_btn.config(state=tk.NORMAL,
                             bg=t["red"], fg=t["accent_fg"])
        self._status_label.config(text="Searching documents...", fg=t["orange"])

        # Start elapsed timer
        self._stream_start = time.time()
        self._update_elapsed()

        # Dispatch via model
        self._model.query(
            text=question,
            top_k=top_k,
            callback=lambda resp: safe_after(self, 0, self._on_query_done, resp),
            error_callback=lambda exc: safe_after(self, 0, self._on_query_error, exc),
        )

    def _on_stop(self, event=None):
        """Handle Stop button click or Escape key."""
        if self._model:
            self._model.cancel_query()
        self._finish_query_ui()
        t = current_theme()
        self._status_label.config(text="Query cancelled.", fg=t["orange"])

    def _on_query_done(self, response):
        """Handle successful query response (runs on main thread via safe_after)."""
        t = current_theme()

        # Set query path badge
        path = getattr(response, "query_path", "SEMANTIC")
        path_color_key = _PATH_COLORS.get(path, "fg")
        self._path_badge.config(
            text=" {} ".format(path),
            fg=t["accent_fg"],
            bg=t.get(path_color_key, t["accent"]),
        )

        # Set confidence badge
        confidence = getattr(response, "confidence", "")
        conf_color_key = _CONFIDENCE_COLORS.get(confidence, "gray")
        self._confidence_badge.config(
            text=" {} ".format(confidence),
            fg=t["accent_fg"],
            bg=t.get(conf_color_key, t["gray"]),
        )

        # Display answer
        answer = getattr(response, "answer", "(no answer)")
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", answer)
        self.answer_text.config(state=tk.DISABLED)

        # Update sources
        sources = getattr(response, "sources", []) or []
        self._update_sources(sources)

        # Metrics line
        latency = getattr(response, "latency_ms", 0)
        chunks = getattr(response, "chunks_used", 0)
        in_tok = getattr(response, "input_tokens", 0)
        out_tok = getattr(response, "output_tokens", 0)
        metrics_parts = [
            "Latency: {}ms".format(latency),
            "Chunks: {}".format(chunks),
        ]
        if in_tok or out_tok:
            metrics_parts.append("Tokens: {}in/{}out".format(in_tok, out_tok))
        self._metrics_label.config(text="  |  ".join(metrics_parts), fg=t["fg"])

        # Update status bar query path
        self._notify_status_bar(path)

        self._finish_query_ui()
        self._status_label.config(text="", fg=t["gray"])

    def _on_query_error(self, exc):
        """Handle query error (runs on main thread via safe_after)."""
        t = current_theme()
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", "Error: {}".format(str(exc)))
        self.answer_text.config(state=tk.DISABLED)

        self._confidence_badge.config(
            text=" ERROR ", fg=t["accent_fg"], bg=t["red"],
        )
        self._finish_query_ui()
        self._status_label.config(text="Query failed.", fg=t["red"])

    def _finish_query_ui(self):
        """Restore UI to idle state after query completes or cancels."""
        t = current_theme()
        ready = self._model and self._model.pipeline is not None
        if ready:
            self.ask_btn.config(
                state=tk.NORMAL, bg=t["accent"], fg=t["accent_fg"],
            )
        else:
            self.ask_btn.config(
                state=tk.DISABLED, bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            )
        self.stop_btn.config(
            state=tk.DISABLED, bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
        )

        # Stop elapsed timer
        if self._elapsed_timer_id is not None:
            try:
                self.after_cancel(self._elapsed_timer_id)
            except Exception:
                pass
            self._elapsed_timer_id = None

    # ------------------------------------------------------------------
    # Elapsed timer
    # ------------------------------------------------------------------

    def _update_elapsed(self):
        """Update elapsed time display every 100ms during a query."""
        if self._model and self._model.is_querying:
            elapsed = time.time() - self._stream_start
            self._elapsed_label.config(text="{:.1f}s".format(elapsed))
            self._elapsed_timer_id = self.after(100, self._update_elapsed)
        else:
            elapsed = time.time() - self._stream_start
            self._elapsed_label.config(text="{:.1f}s".format(elapsed))

    # ------------------------------------------------------------------
    # Sources expandable section
    # ------------------------------------------------------------------

    def _update_sources(self, sources):
        """Update the sources expandable section."""
        count = len(sources)
        prefix = "-" if self._sources_expanded else "+"
        self._sources_toggle_btn.config(
            text="{} Sources ({})".format(prefix, count)
        )
        self._sources_detail.config(state=tk.NORMAL)
        self._sources_detail.delete("1.0", tk.END)
        if sources:
            self._sources_detail.insert("1.0", "\n".join(sources))
        else:
            self._sources_detail.insert("1.0", "(no sources)")
        self._sources_detail.config(state=tk.DISABLED)

    def _toggle_sources(self):
        """Toggle the sources detail section visibility."""
        if self._sources_expanded:
            self._sources_detail.pack_forget()
            self._sources_expanded = False
            text = self._sources_toggle_btn.cget("text")
            self._sources_toggle_btn.config(text=text.replace("-", "+", 1))
        else:
            self._sources_detail.pack(fill=tk.X, pady=(4, 0))
            self._sources_expanded = True
            text = self._sources_toggle_btn.cget("text")
            self._sources_toggle_btn.config(text=text.replace("+", "-", 1))

    # ------------------------------------------------------------------
    # Status bar integration
    # ------------------------------------------------------------------

    def _notify_status_bar(self, path_name):
        """Push query path to the status bar if accessible."""
        try:
            widget = self.master
            while widget is not None:
                if hasattr(widget, "status_bar"):
                    widget.status_bar.set_query_path(path_name)
                    break
                widget = getattr(widget, "master", None)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self, t):
        """Re-apply theme colors to all widgets."""
        self.configure(bg=t["panel_bg"], fg=t["accent"])

        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                try:
                    child.configure(bg=t["panel_bg"])
                except Exception:
                    pass

        self.question_entry.configure(
            bg=t["input_bg"], fg=t["input_fg"], insertbackground=t["fg"],
        )
        self.answer_text.configure(
            bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], selectbackground=t["accent"],
        )
        self._status_label.configure(bg=t["panel_bg"])
        self._metrics_label.configure(bg=t["panel_bg"])
        self._elapsed_label.configure(bg=t["panel_bg"])
        self._sources_toggle_btn.configure(bg=t["panel_bg"], fg=t["accent"])
        self._sources_detail.configure(bg=t["input_bg"], fg=t["input_fg"])

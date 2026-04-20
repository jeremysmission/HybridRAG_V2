"""Query panel -- clean chat-style interface for asking questions and viewing answers.

Inspired by Perplexity/ChatGPT layout: question input at top, streaming answer
with inline [1][2] footnotes, collapsible source cards below.
Admin controls (endpoint, top-k, IBIT, advanced retrieval) are hidden behind
an Admin menu accessible from the nav bar -- not cluttering the user surface.

V1 repurpose lineage:
  - Master-detail sidebar pattern: V1 reference_panel.py:77-153
  - Source rendering (path+chunks dict): V1 query_panel_query_render_runtime.py:273-285
  - PanedWindow split: V1 query_panel.py:288-297
"""

import json
import re
import tkinter as tk
from tkinter import ttk
import threading
import time
import logging
import queue
from datetime import datetime
from pathlib import Path

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_SMALL, FONT_MONO
from src.gui.helpers.safe_after import safe_after

logger = logging.getLogger(__name__)

_PATH_COLORS = {
    "SEMANTIC": "accent",
    "ENTITY": "green",
    "AGGREGATE": "orange",
    "AGGREGATION_GREEN": "green",
    "AGGREGATION_YELLOW": "orange",
    "AGGREGATION_RED": "red",
    "LOGISTICS_GUARD": "orange",
    "TABULAR": "orange",
    "COMPLEX": "red",
}

_CONFIDENCE_COLORS = {
    "HIGH": "green",
    "PARTIAL": "orange",
    "NOT_FOUND": "red",
    "GREEN": "green",
    "YELLOW": "orange",
    "RED": "red",
    "LLM_UNAVAILABLE": "orange",
    "NOT_SUPPORTED": "orange",
}


class QueryPanel(tk.Frame):
    """Clean chat-style query panel.

    User surface: question bar, answer area with footnotes, source cards.
    Admin controls accessible via toggle drawer at bottom.
    """

    def __init__(self, parent, model):
        t = current_theme()
        super().__init__(parent, bg=t["panel_bg"])
        self._model = model
        self._streaming = False
        self._stream_start = 0.0
        self._elapsed_timer_id = None
        self._token_queue = queue.Queue()
        self._token_pump_id = None
        self._last_sources = []
        self._last_response = None
        self._source_cards_expanded = False
        self._admin_visible = False

        self._build_widgets(t)
        self.after(200, self._check_ready)

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_widgets(self, t):
        # Main vertical layout: question bar -> answer -> sources -> admin drawer

        # -- Question bar (clean, prominent) --
        q_frame = tk.Frame(self, bg=t["panel_bg"])
        q_frame.pack(fill=tk.X, padx=16, pady=(16, 8))

        self.question_entry = tk.Entry(
            q_frame, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=2,
        )
        self.question_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.question_entry.insert(0, "Ask a question...")
        self.question_entry.bind("<FocusIn>", self._on_entry_focus)
        self.question_entry.bind("<Return>", self._on_ask)
        self.question_entry.bind("<Escape>", self._on_stop)

        self.ask_btn = tk.Button(
            q_frame, text="Ask", command=self._on_ask, width=8,
            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            font=FONT_BOLD, relief=tk.FLAT, bd=0,
            padx=16, pady=6, state=tk.DISABLED,
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"],
        )
        self.ask_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.stop_btn = tk.Button(
            q_frame, text="Stop", command=self._on_stop, width=6,
            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            font=FONT, relief=tk.FLAT, bd=0,
            padx=12, pady=6, state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(4, 0))

        # -- Status line (minimal, below question bar) --
        self._status_label = tk.Label(
            self, text="", fg=t["gray"], anchor=tk.W,
            bg=t["panel_bg"], font=FONT_SMALL, padx=16,
        )
        self._status_label.pack(fill=tk.X)

        # -- Answer area --
        answer_frame = tk.Frame(self, bg=t["panel_bg"])
        answer_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 0))

        scrollbar = tk.Scrollbar(answer_frame, orient=tk.VERTICAL)
        self.answer_text = tk.Text(
            answer_frame, height=14, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=1,
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.answer_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.answer_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Text tags for formatting
        self.answer_text.tag_configure("footnote",
            foreground=t["accent"], font=FONT_BOLD)
        self.answer_text.tag_configure("tier_green",
            foreground="#4caf50", font=FONT_BOLD)
        self.answer_text.tag_configure("tier_yellow",
            foreground="#ff9800", font=FONT_BOLD)
        self.answer_text.tag_configure("tier_red",
            foreground="#f44336", font=FONT_BOLD)
        self.answer_text.tag_configure("table_header",
            foreground="#0078d4", font=FONT_BOLD)
        self.answer_text.tag_configure("section_header",
            foreground="#ffffff", font=FONT_BOLD)
        self.answer_text.tag_configure("evidence_dim",
            foreground="#a0a0a0")
        self.answer_text.tag_configure("substrate_footer",
            foreground="#777777", font=FONT_SMALL)

        # -- Metrics line (compact, right-aligned) --
        self._metrics_label = tk.Label(
            self, text="", anchor=tk.E, fg=t["gray"],
            bg=t["panel_bg"], font=FONT_SMALL, padx=16,
        )
        self._metrics_label.pack(fill=tk.X)

        # -- Source cards section --
        self._sources_frame = tk.Frame(self, bg=t["panel_bg"])
        self._sources_frame.pack(fill=tk.X, padx=16, pady=(4, 0))

        self._sources_toggle_btn = tk.Button(
            self._sources_frame, text="+ Sources (0)", font=FONT,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            command=self._toggle_source_cards, cursor="hand2",
            activebackground=t["panel_bg"], activeforeground=t["accent_hover"],
        )
        self._sources_toggle_btn.pack(anchor=tk.W)

        self._source_cards_container = tk.Frame(
            self._sources_frame, bg=t["panel_bg"])

        # -- Action buttons (copy, export) --
        self._action_frame = tk.Frame(self, bg=t["panel_bg"])
        self._action_frame.pack(fill=tk.X, padx=16, pady=(4, 0))

        self._copy_answer_btn = tk.Button(
            self._action_frame, text="Copy Answer", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_answer,
        )
        self._copy_answer_btn.pack(side=tk.LEFT)

        self._copy_sources_btn = tk.Button(
            self._action_frame, text="Copy Sources", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_sources,
        )
        self._copy_sources_btn.pack(side=tk.LEFT, padx=(6, 0))

        self._action_frame.pack_forget()

        # -- Feedback buttons --
        self._feedback_frame = tk.Frame(self, bg=t["panel_bg"])
        self._feedback_frame.pack(fill=tk.X, padx=16, pady=(4, 0))

        self._feedback_label = tk.Label(
            self._feedback_frame, text="Was this helpful?",
            bg=t["panel_bg"], fg=t["gray"], font=FONT_SMALL,
        )
        self._feedback_label.pack(side=tk.LEFT)

        self._feedback_btns = {}
        for label, value in [
            ("\u2714 Helpful", "helpful"),
            ("\u2718 Not Helpful", "not_helpful"),
        ]:
            btn = tk.Button(
                self._feedback_frame, text=label, font=FONT_SMALL,
                bg=t["panel_bg"], fg=t["fg"], relief=tk.FLAT,
                padx=8, pady=2, cursor="hand2",
                command=lambda v=value: self._on_feedback(v),
            )
            btn.pack(side=tk.LEFT, padx=(6, 0))
            self._feedback_btns[value] = btn

        self._feedback_frame.pack_forget()

        # -- Admin drawer (hidden by default) --
        self._admin_toggle = tk.Button(
            self, text="\u2699 Admin", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["gray"], relief=tk.FLAT, bd=0,
            command=self._toggle_admin, cursor="hand2",
        )
        self._admin_toggle.pack(anchor=tk.W, padx=16, pady=(8, 0))

        self._admin_frame = tk.Frame(self, bg=t["panel_bg"])
        self._build_admin_controls(t)

        # Session log
        self._session_log_dir = Path("data/query_sessions")
        self._session_log_dir.mkdir(parents=True, exist_ok=True)
        self._current_session = None

    def _build_admin_controls(self, t):
        """Build admin-only controls inside the collapsible drawer."""

        # -- IBIT strip --
        ibit_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        ibit_row.pack(fill=tk.X, pady=(4, 2))

        self._ibit_label = tk.Label(
            ibit_row, text="IBIT: checking...",
            font=FONT_SMALL, bg=t["panel_bg"], fg=t["orange"],
            anchor=tk.W, cursor="hand2",
        )
        self._ibit_label.pack(side=tk.LEFT)
        self._ibit_label.bind("<Button-1>", self._show_ibit_detail)
        self._ibit_dots = {}
        self._ibit_results = None
        self.after(1500, self._run_ibit_async)

        # -- Badges row (path + confidence + evidence) --
        badge_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        badge_row.pack(fill=tk.X, pady=(2, 2))

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

        self._evidence_badge = tk.Label(
            badge_row, text="", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["gray"], padx=8, pady=2,
        )
        self._evidence_badge.pack(side=tk.LEFT, padx=(8, 0))

        self._elapsed_label = tk.Label(
            badge_row, text="", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["gray"],
        )
        self._elapsed_label.pack(side=tk.RIGHT)

        # -- Endpoint switch --
        endpoint_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        endpoint_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(
            endpoint_row, text="AI Endpoint:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT_SMALL,
        ).pack(side=tk.LEFT)

        self._endpoint_var = tk.StringVar(value="GPT-4o")
        self._endpoint_ready = False
        self._endpoint_combo = ttk.Combobox(
            endpoint_row, textvariable=self._endpoint_var,
            values=["GPT-4o", "phi4:14b"],
            state="readonly", width=12, font=FONT_SMALL,
        )
        self._endpoint_combo.pack(side=tk.LEFT, padx=(8, 0))
        self._endpoint_combo.bind("<<ComboboxSelected>>", self._on_endpoint_change)

        self._endpoint_status = tk.Label(
            endpoint_row, text="warming up...", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["orange"],
        )
        self._endpoint_status.pack(side=tk.LEFT, padx=(8, 0))

        self._endpoint_detect_start = time.time()
        self._endpoint_detect_timeout = 60
        self.after(2000, self._auto_detect_endpoint)
        self.after(500, self._mark_endpoint_ready)

        # -- Top-K --
        topk_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        topk_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(topk_row, text="Top-K:", bg=t["panel_bg"],
                 fg=t["fg"], font=FONT_SMALL).pack(side=tk.LEFT)

        self._topk_var = tk.IntVar(value=10)
        tk.Spinbox(
            topk_row, from_=1, to=50, textvariable=self._topk_var,
            width=5, font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"],
            buttonbackground=t["input_bg"], relief=tk.FLAT, bd=1,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # -- Advanced retrieval controls --
        cfg = self._model.config if self._model else None
        retrieval = cfg.retrieval if cfg and hasattr(cfg, "retrieval") else None

        cp_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        cp_row.pack(fill=tk.X, pady=1)
        tk.Label(cp_row, text="Candidate Pool:", bg=t["panel_bg"],
                 fg=t["fg"], font=FONT_SMALL, width=16, anchor=tk.W
                 ).pack(side=tk.LEFT)
        self._candidate_pool_var = tk.IntVar(
            value=retrieval.candidate_pool if retrieval else 30)
        tk.Spinbox(cp_row, from_=10, to=200,
                   textvariable=self._candidate_pool_var,
                   width=5, font=FONT_SMALL, bg=t["input_bg"],
                   fg=t["input_fg"], relief=tk.FLAT, bd=1
                   ).pack(side=tk.LEFT, padx=(4, 0))

        ms_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        ms_row.pack(fill=tk.X, pady=1)
        tk.Label(ms_row, text="Min Score:", bg=t["panel_bg"],
                 fg=t["fg"], font=FONT_SMALL, width=16, anchor=tk.W
                 ).pack(side=tk.LEFT)
        self._min_score_var = tk.DoubleVar(
            value=retrieval.min_score if retrieval else 0.0)
        tk.Scale(ms_row, from_=0.0, to=1.0, resolution=0.05,
                 orient=tk.HORIZONTAL, variable=self._min_score_var,
                 length=120, font=FONT_SMALL, bg=t["panel_bg"],
                 fg=t["fg"], troughcolor=t["input_bg"],
                 highlightthickness=0).pack(side=tk.LEFT, padx=(4, 0))

        rn_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        rn_row.pack(fill=tk.X, pady=1)
        tk.Label(rn_row, text="Reranker Top-N:", bg=t["panel_bg"],
                 fg=t["fg"], font=FONT_SMALL, width=16, anchor=tk.W
                 ).pack(side=tk.LEFT)
        self._reranker_topn_var = tk.IntVar(
            value=retrieval.reranker_top_n if retrieval else 5)
        tk.Spinbox(rn_row, from_=1, to=50,
                   textvariable=self._reranker_topn_var,
                   width=5, font=FONT_SMALL, bg=t["input_bg"],
                   fg=t["input_fg"], relief=tk.FLAT, bd=1
                   ).pack(side=tk.LEFT, padx=(4, 0))

        rt_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        rt_row.pack(fill=tk.X, pady=1)
        self._reranker_enabled_var = tk.BooleanVar(
            value=retrieval.reranker_enabled if retrieval else True)
        tk.Checkbutton(
            rt_row, text="Reranker Enabled",
            variable=self._reranker_enabled_var,
            bg=t["panel_bg"], fg=t["fg"], font=FONT_SMALL,
            selectcolor=t["input_bg"], activebackground=t["panel_bg"],
        ).pack(side=tk.LEFT)

        gnd_row = tk.Frame(self._admin_frame, bg=t["panel_bg"])
        gnd_row.pack(fill=tk.X, pady=1)
        self._grounded_only_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            gnd_row, text="Grounded Only",
            variable=self._grounded_only_var,
            bg=t["panel_bg"], fg=t["fg"], font=FONT_SMALL,
            selectcolor=t["input_bg"], activebackground=t["panel_bg"],
        ).pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Admin drawer toggle
    # ------------------------------------------------------------------

    def _toggle_admin(self):
        if self._admin_visible:
            self._admin_frame.pack_forget()
            self._admin_toggle.config(text="\u2699 Admin")
            self._admin_visible = False
        else:
            self._admin_frame.pack(fill=tk.X, padx=16, pady=(0, 8))
            self._admin_toggle.config(text="\u2699 Admin (hide)")
            self._admin_visible = True

    # ------------------------------------------------------------------
    # Placeholder handling
    # ------------------------------------------------------------------

    def _on_entry_focus(self, event=None):
        if self.question_entry.get() == "Ask a question...":
            self.question_entry.delete(0, tk.END)

    # ------------------------------------------------------------------
    # Endpoint management (admin)
    # ------------------------------------------------------------------

    _ENDPOINT_MAP = {
        "GPT-4o": {"model": "gpt-4o", "deployment": "gpt-4o", "provider": "auto"},
        "phi4:14b": {"model": "phi4:14b", "deployment": "", "provider": "ollama"},
    }

    @staticmethod
    def _widget_exists(widget):
        """Best-effort existence check for delayed Tk callbacks."""
        if widget is None:
            return False
        try:
            return bool(int(widget.winfo_exists()))
        except Exception:
            return False

    def _safe_config_widget(self, widget, **kwargs):
        """Apply widget config only while the target widget still exists."""
        if not self._widget_exists(widget):
            return
        try:
            widget.config(**kwargs)
        except Exception:
            pass

    def _dispatch_ui_callback(self, callback):
        """Route background-thread UI work back onto the Tk main thread."""
        safe_after(self, 0, callback)

    def _restore_source_card_style(self, widget, border_color):
        """Reset card highlighting if the referenced card is still alive."""
        self._safe_config_widget(
            widget,
            highlightbackground=border_color,
            highlightthickness=1,
        )

    def _mark_endpoint_ready(self):
        self._endpoint_ready = True

    def _on_endpoint_change(self, event=None):
        if not self._endpoint_ready:
            return
        label = self._endpoint_var.get()
        mapping = self._ENDPOINT_MAP.get(label)
        if not mapping:
            return
        t = current_theme()
        self._endpoint_status.config(text="switching...", fg=t["orange"])
        if self._model and self._model.config:
            self._model.config.llm.model = mapping["model"]
            self._model.config.llm.deployment = mapping["deployment"]
            self._model.config.llm.provider = mapping["provider"]
        try:
            import yaml
            config_path = Path(__file__).resolve().parents[3] / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
                if "llm" not in raw:
                    raw["llm"] = {}
                raw["llm"]["model"] = mapping["model"]
                raw["llm"]["deployment"] = mapping["deployment"]
                raw["llm"]["provider"] = mapping["provider"]
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.dump(raw, f, default_flow_style=False,
                              allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.warning("Failed to save endpoint config: %s", e)
        self._endpoint_status.config(
            text="{} selected".format(label), fg=t["orange"])
        self._endpoint_detect_start = time.time()
        self.after(1000, self._auto_detect_endpoint)

    def _auto_detect_endpoint(self):
        t = current_theme()

        def _probe():
            if self._model and self._model.llm_available:
                client = getattr(self._model, "_llm_client", None)
                if client:
                    provider = getattr(client, "_provider", "unknown")
                    if provider == "ollama":
                        detected, status, color = "phi4:14b", "phi4 (local)", t["green"]
                    else:
                        detected, status, color = "GPT-4o", "GPT-4o (online)", t["green"]

                    def _update():
                        if not self._widget_exists(self):
                            return
                        try:
                            self._endpoint_var.set(detected)
                        except Exception:
                            pass
                        self._safe_config_widget(
                            self._endpoint_status, text=status, fg=color)
                    self._dispatch_ui_callback(_update)
                    return
            try:
                import urllib.request
                req = urllib.request.urlopen(
                    "http://localhost:11434/api/tags", timeout=3)
                if req.status == 200:
                    def _fallback():
                        if not self._widget_exists(self):
                            return
                        try:
                            self._endpoint_var.set("phi4:14b")
                        except Exception:
                            pass
                        self._safe_config_widget(
                            self._endpoint_status,
                            text="phi4 (local fallback)",
                            fg=t["orange"],
                        )
                    self._dispatch_ui_callback(_fallback)
                    return
            except Exception:
                pass
            elapsed = time.time() - self._endpoint_detect_start
            if elapsed > self._endpoint_detect_timeout:
                def _failed():
                    self._safe_config_widget(
                        self._endpoint_status,
                        text="no AI connected",
                        fg=t["red"],
                    )
                self._dispatch_ui_callback(_failed)
            else:
                remaining = int(self._endpoint_detect_timeout - elapsed)
                def _retry():
                    self._safe_config_widget(
                        self._endpoint_status,
                        text="warming up... ({}s)".format(remaining),
                        fg=t["orange"],
                    )
                    if self._widget_exists(self):
                        try:
                            self.after(5000, self._auto_detect_endpoint)
                        except Exception:
                            pass
                self._dispatch_ui_callback(_retry)

        threading.Thread(target=_probe, daemon=True).start()

    # ------------------------------------------------------------------
    # Ready check
    # ------------------------------------------------------------------

    def _check_ready(self):
        t = current_theme()
        if self._model and self._model.pipeline is not None:
            self.ask_btn.config(state=tk.NORMAL, bg=t["accent"],
                                fg=t["accent_fg"])
        else:
            self.after(500, self._check_ready)

    def set_ready(self, ready):
        t = current_theme()
        if ready:
            self.ask_btn.config(state=tk.NORMAL, bg=t["accent"],
                                fg=t["accent_fg"])
        else:
            self.ask_btn.config(state=tk.DISABLED, bg=t["inactive_btn_bg"],
                                fg=t["inactive_btn_fg"])

    # ------------------------------------------------------------------
    # Query lifecycle
    # ------------------------------------------------------------------

    def _on_ask(self, event=None):
        question = self.question_entry.get().strip()
        if not question or question == "Ask a question...":
            return
        if self._model is None or self._model.is_querying:
            return

        t = current_theme()
        top_k = self._topk_var.get()

        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.config(state=tk.DISABLED)
        self._clear_source_cards()

        self._path_badge.config(text="", fg=t["gray"])
        self._confidence_badge.config(text="", fg=t["gray"])
        self._evidence_badge.config(text="", fg=t["gray"], bg=t["panel_bg"])

        self.ask_btn.config(state=tk.DISABLED,
                            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"])
        self.stop_btn.config(state=tk.NORMAL, bg=t["red"], fg=t["accent_fg"])

        self._stream_start = time.time()
        self._update_elapsed()

        def _phase_update():
            elapsed = time.time() - self._stream_start
            if self._model and self._model.is_querying:
                if elapsed < 2:
                    self._status_label.config(
                        text="Searching...", fg=t["orange"])
                elif elapsed < 8:
                    self._status_label.config(
                        text="Searching 10.4M documents...", fg=t["orange"])
                else:
                    self._status_label.config(
                        text="Generating answer... ({:.0f}s)".format(elapsed),
                        fg=t["orange"])
                self.after(500, _phase_update)
        self.after(500, _phase_update)

        self._model.query(
            text=question, top_k=top_k,
            callback=lambda resp: safe_after(
                self, 0, self._on_query_done, resp),
            error_callback=lambda exc: safe_after(
                self, 0, self._on_query_error, exc),
        )

    def _on_stop(self, event=None):
        if self._model:
            self._model.cancel_query()
        self._finish_query_ui()
        t = current_theme()
        self._status_label.config(text="Cancelled.", fg=t["orange"])

    def _on_query_done(self, response):
        t = current_theme()
        self._last_response = response

        # Admin badges
        path = getattr(response, "query_path", "SEMANTIC")
        path_color_key = _PATH_COLORS.get(path, "fg")
        self._path_badge.config(
            text=" {} ".format(path), fg=t["accent_fg"],
            bg=t.get(path_color_key, t["accent"]))

        confidence = getattr(response, "confidence", "")
        conf_color_key = _CONFIDENCE_COLORS.get(confidence, "gray")
        self._confidence_badge.config(
            text=" {} ".format(confidence), fg=t["accent_fg"],
            bg=t.get(conf_color_key, t["gray"]))

        # Display answer with inline footnotes
        answer = getattr(response, "answer", "") or ""
        sources = getattr(response, "sources", []) or []
        self._last_sources = sources

        if not answer.strip() or answer.strip() == "[NOT_FOUND]":
            answer = (
                "No relevant documents found for this query.\n\n"
                "Try rephrasing with more specific terms, "
                "a CDRL code, site name, or date."
            )

        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        is_aggregation = path.startswith("AGGREGATION_")
        if is_aggregation:
            self._insert_formatted_aggregation(answer)
        else:
            self._insert_answer_with_footnotes(answer, sources)
        self.answer_text.config(state=tk.DISABLED)

        # Build source cards
        self._build_source_cards(sources)

        # Metrics
        latency = getattr(response, "latency_ms", 0)
        chunks = getattr(response, "chunks_used", 0)
        in_tok = getattr(response, "input_tokens", 0)
        out_tok = getattr(response, "output_tokens", 0)
        parts = ["{}ms".format(latency), "{} chunks".format(chunks)]
        if in_tok or out_tok:
            parts.append("{}in/{}out tokens".format(in_tok, out_tok))
        self._metrics_label.config(text="  |  ".join(parts), fg=t["gray"])

        self._notify_status_bar(path)

        question = self.question_entry.get().strip()
        self._current_session = self._log_session(question, response)
        self._feedback_frame.pack(fill=tk.X, padx=16, pady=(4, 0))
        self._action_frame.pack(fill=tk.X, padx=16, pady=(4, 0))
        for btn in self._feedback_btns.values():
            btn.config(bg=t["panel_bg"], fg=t["fg"])

        self._finish_query_ui()
        elapsed = time.time() - self._stream_start
        self._status_label.config(
            text="Done ({:.1f}s)".format(elapsed), fg=t["green"])

    # ------------------------------------------------------------------
    # Inline footnotes (Perplexity-style)
    # ------------------------------------------------------------------

    def _insert_answer_with_footnotes(self, answer, sources):
        """Insert answer text, converting [Source N: ...] references to
        sequential user-facing [1], [2], [3] footnotes.

        The LLM cites internal chunk numbers (e.g. [Source 14: file.pdf])
        which can be high and non-sequential. We remap to display numbers
        by order of first appearance so the user always sees [1], [2], etc.
        Repeated citations of the same source reuse the same display number.
        """
        source_filenames = []
        for s in sources:
            if isinstance(s, str):
                name = s.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            else:
                name = str(s)
            source_filenames.append(name.lower())

        footnote_pattern = re.compile(
            r'\[Source(?:\s+(\d+))?:\s*([^\]]+)\]', re.IGNORECASE)

        # Pass 1: scan all citations to build sequential display mapping.
        # Key = source index (0-based into sources list), value = display num.
        # Order is by first appearance in the answer text.
        self._display_num_map = {}
        next_display = 1
        for match in footnote_pattern.finditer(answer):
            src_idx = self._resolve_source_index(
                match.group(1), match.group(2), source_filenames)
            if src_idx not in self._display_num_map:
                self._display_num_map[src_idx] = next_display
                next_display += 1

        # Pass 2: insert text with remapped display numbers.
        last_end = 0
        for match in footnote_pattern.finditer(answer):
            self.answer_text.insert(tk.END, answer[last_end:match.start()])

            src_idx = self._resolve_source_index(
                match.group(1), match.group(2), source_filenames)
            display_num = self._display_num_map.get(src_idx, next_display)

            tag_name = "fn_d{}".format(display_num)
            self.answer_text.tag_configure(tag_name,
                foreground=current_theme()["accent"], font=FONT_BOLD,
                underline=True)
            self.answer_text.insert(
                tk.END, "[{}]".format(display_num), tag_name)
            self.answer_text.tag_bind(
                tag_name, "<Button-1>",
                lambda e, n=display_num: self._scroll_to_source_card(n))

            last_end = match.end()

        self.answer_text.insert(tk.END, answer[last_end:])

    @staticmethod
    def _resolve_source_index(explicit_num_str, cited_name_raw,
                              source_filenames):
        """Map a citation back to a 0-based source index.

        Handles both forms:
          [Source 3: filename]  -> uses explicit number (1-based -> 0-based)
          [Source: filename]    -> fuzzy-matches against source_filenames
        Returns a 0-based index, or -1 if unresolvable.
        """
        cited_name = cited_name_raw.strip().lower()
        # Strip trailing ", section" or similar suffixes for matching
        cited_base = cited_name.split(",")[0].strip()

        if explicit_num_str:
            idx = int(explicit_num_str) - 1
            if 0 <= idx < len(source_filenames):
                return idx

        # Fuzzy match by filename substring
        for i, sname in enumerate(source_filenames):
            if cited_base in sname or sname in cited_base:
                return i

        # No match -- return sentinel so it still gets a unique display number
        return -(hash(cited_name) % 10000) - 1

    # ------------------------------------------------------------------
    # Source cards (collapsible, below answer)
    # ------------------------------------------------------------------

    def _build_source_cards(self, sources):
        """Build source cards using display numbering from footnote pass.

        Only sources that were actually cited in the answer get cards,
        ordered by their display number. This keeps the card list aligned
        with the [1], [2], [3] footnotes the user sees.
        """
        self._clear_source_cards()
        display_map = getattr(self, "_display_num_map", {})

        # Build cards only for cited sources, ordered by display number
        cited_pairs = sorted(display_map.items(), key=lambda x: x[1])

        # If no citations were found (e.g. aggregation or no-source answer),
        # fall back to showing all sources with sequential numbering
        if not cited_pairs and sources:
            cited_pairs = [(i, i + 1) for i in range(len(sources))]

        shown_count = len(cited_pairs)
        self._sources_toggle_btn.config(
            text="+ Sources ({})".format(shown_count))
        self._source_cards_expanded = False

        t = current_theme()
        for src_idx, display_num in cited_pairs:
            if src_idx < 0 or src_idx >= len(sources):
                continue

            source = sources[src_idx]
            if isinstance(source, str):
                filepath = source
                filename = source.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            else:
                filepath = str(source)
                filename = filepath.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]

            card = tk.Frame(
                self._source_cards_container, bg=t["input_bg"],
                highlightbackground=t["border"], highlightthickness=1,
                padx=8, pady=6)
            card.pack(fill=tk.X, pady=(2, 0))
            card._source_index = display_num

            header = tk.Label(
                card,
                text="[{}] {}".format(display_num, filename),
                font=FONT_BOLD, bg=t["input_bg"], fg=t["accent"],
                anchor=tk.W,
            )
            header.pack(fill=tk.X)

            path_label = tk.Label(
                card,
                text=filepath,
                font=FONT_SMALL, bg=t["input_bg"], fg=t["gray"],
                anchor=tk.W,
            )
            path_label.pack(fill=tk.X)

    def _clear_source_cards(self):
        for child in self._source_cards_container.winfo_children():
            child.destroy()

    def _toggle_source_cards(self):
        if self._source_cards_expanded:
            self._source_cards_container.pack_forget()
            self._source_cards_expanded = False
            text = self._sources_toggle_btn.cget("text")
            self._sources_toggle_btn.config(
                text=text.replace("-", "+", 1))
        else:
            self._source_cards_container.pack(fill=tk.X, pady=(4, 0))
            self._source_cards_expanded = True
            text = self._sources_toggle_btn.cget("text")
            self._sources_toggle_btn.config(
                text=text.replace("+", "-", 1))

    def _scroll_to_source_card(self, footnote_num):
        """Expand source cards and highlight the referenced card."""
        if not self._source_cards_expanded:
            self._toggle_source_cards()
        t = current_theme()
        for child in self._source_cards_container.winfo_children():
            idx = getattr(child, "_source_index", None)
            if idx == footnote_num:
                self._safe_config_widget(
                    child,
                    highlightbackground=t["accent"],
                    highlightthickness=2,
                )
                safe_after(
                    self,
                    2000,
                    self._restore_source_card_style,
                    child,
                    t["border"],
                )
            else:
                self._safe_config_widget(
                    child,
                    highlightbackground=t["border"],
                    highlightthickness=1,
                )

    # ------------------------------------------------------------------
    # Aggregation formatting (preserved from original)
    # ------------------------------------------------------------------

    def _insert_formatted_aggregation(self, text):
        tier_tag_map = {
            "GREEN": "tier_green", "YELLOW": "tier_yellow", "RED": "tier_red"}
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("**Confidence tier:**"):
                for tier, tag in tier_tag_map.items():
                    if tier in stripped:
                        self.answer_text.insert(tk.END, line + "\n", tag)
                        break
                else:
                    self.answer_text.insert(tk.END, line + "\n")
            elif stripped.startswith("## ") or stripped.startswith("### "):
                self.answer_text.insert(tk.END, line + "\n", "section_header")
            elif stripped.startswith("| Rank") or stripped.startswith("| ---"):
                self.answer_text.insert(tk.END, line + "\n", "table_header")
            elif stripped.startswith("| ") and "|" in stripped[1:]:
                self.answer_text.insert(tk.END, line + "\n")
            elif stripped.startswith("*Substrate coverage:*") or stripped.startswith("*This answer was"):
                self.answer_text.insert(tk.END, line + "\n", "substrate_footer")
            elif stripped.startswith("- ") and any(
                    k in stripped for k in
                    ("year=", "incident=", "confidence=")):
                self.answer_text.insert(tk.END, line + "\n", "evidence_dim")
            elif stripped.startswith("**Tier:** RED") or stripped.startswith("**Reason:**"):
                self.answer_text.insert(tk.END, line + "\n", "tier_red")
            else:
                self.answer_text.insert(tk.END, line + "\n")

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _on_query_error(self, exc):
        t = current_theme()
        exc_str = str(exc).lower()

        if "timeout" in exc_str or "timed out" in exc_str:
            message = "Query timed out. Try simplifying your question or reducing Top-K."
        elif "connection" in exc_str or "refused" in exc_str:
            message = "Could not connect to the search backend. Check that the LLM service is running."
        else:
            message = "Query failed: {}".format(str(exc))

        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", message)
        self.answer_text.config(state=tk.DISABLED)

        self._finish_query_ui()
        self._status_label.config(text="Error", fg=t["red"])

    def _finish_query_ui(self):
        t = current_theme()
        ready = self._model and self._model.pipeline is not None
        if ready:
            self.ask_btn.config(state=tk.NORMAL, bg=t["accent"],
                                fg=t["accent_fg"])
        else:
            self.ask_btn.config(state=tk.DISABLED, bg=t["inactive_btn_bg"],
                                fg=t["inactive_btn_fg"])
        self.stop_btn.config(state=tk.DISABLED, bg=t["inactive_btn_bg"],
                             fg=t["inactive_btn_fg"])
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
        if self._model and self._model.is_querying:
            elapsed = time.time() - self._stream_start
            self._elapsed_label.config(text="{:.1f}s".format(elapsed))
            self._elapsed_timer_id = self.after(100, self._update_elapsed)
        else:
            elapsed = time.time() - self._stream_start
            self._elapsed_label.config(text="{:.1f}s".format(elapsed))

    # ------------------------------------------------------------------
    # Status bar integration
    # ------------------------------------------------------------------

    def _notify_status_bar(self, path_name):
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
    # Feedback + Session logging
    # ------------------------------------------------------------------

    def _on_feedback(self, feedback_value):
        t = current_theme()
        if self._current_session:
            self._current_session["feedback"] = feedback_value
            self._current_session["feedback_at"] = datetime.now().isoformat()
            self._save_session(self._current_session)
        for value, btn in self._feedback_btns.items():
            if value == feedback_value:
                btn.config(bg=t["accent"], fg=t["accent_fg"])
            else:
                btn.config(bg=t["panel_bg"], fg=t["gray"])

    def _log_session(self, question, response):
        session = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": getattr(response, "answer", ""),
            "query_path": getattr(response, "query_path", ""),
            "confidence": getattr(response, "confidence", ""),
            "sources": getattr(response, "sources", []) or [],
            "latency_ms": getattr(response, "latency_ms", 0),
            "chunks_used": getattr(response, "chunks_used", 0),
            "feedback": None, "feedback_at": None,
        }
        self._save_session(session)
        return session

    def _save_session(self, session):
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = self._session_log_dir / "sessions_{}.jsonl".format(
                date_str)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(session, default=str) + "\n")
        except Exception as e:
            logger.warning("Failed to save session log: %s", e)

    def _copy_answer(self):
        try:
            text = self.answer_text.get("1.0", tk.END).strip()
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                t = current_theme()
                self._copy_answer_btn.config(text="Copied!", fg=t["green"])
                self.after(2000, lambda: self._copy_answer_btn.config(
                    text="Copy Answer", fg=t["accent"]))
        except Exception:
            pass

    def _copy_sources(self):
        try:
            lines = []
            for s in self._last_sources:
                lines.append(s if isinstance(s, str) else str(s))
            if lines:
                self.clipboard_clear()
                self.clipboard_append("\n".join(lines))
                t = current_theme()
                self._copy_sources_btn.config(text="Copied!", fg=t["green"])
                self.after(2000, lambda: self._copy_sources_btn.config(
                    text="Copy Sources", fg=t["accent"]))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # IBIT (admin only)
    # ------------------------------------------------------------------

    def _run_ibit_async(self):
        if self._model is None:
            t = current_theme()
            self._ibit_label.config(text="IBIT: no model", fg=t["red"])
            return

        def _run():
            try:
                results = self._model.run_ibit()
                safe_after(self, 0, self._update_ibit_display, results)
            except Exception as e:
                logger.warning("IBIT failed: %s", e)
                safe_after(self, 0, lambda: self._ibit_label.config(
                    text="IBIT: error", fg=current_theme()["red"]))

        threading.Thread(target=_run, daemon=True).start()

    def _update_ibit_display(self, results):
        self._ibit_results = results
        t = current_theme()
        for w in list(self._ibit_dots.values()):
            w.destroy()
        self._ibit_dots.clear()

        passed = sum(1 for v in results.values() if v[0])
        total = len(results)

        if passed == total:
            txt, fg = "IBIT: {}/{} OK".format(passed, total), t["green"]
        elif passed > 0:
            txt, fg = "IBIT: {}/{} PARTIAL".format(passed, total), t["orange"]
        else:
            txt, fg = "IBIT: {}/{} FAIL".format(passed, total), t["red"]
        self._ibit_label.config(text=txt, fg=fg)

        for name, (ok, detail, ms) in results.items():
            dot_color = t["green"] if ok else t["red"]
            short = name.replace(" Store", "").replace(
                " Connection", "").replace(" Index", "")
            dot = tk.Label(
                self._ibit_label.master, text=" {} ".format(short),
                font=FONT_SMALL, bg=dot_color, fg=t["accent_fg"],
                padx=4, pady=0)
            dot.pack(side=tk.LEFT, padx=(4, 0))
            self._ibit_dots[name] = dot

    def _show_ibit_detail(self, event=None):
        if not self._ibit_results:
            return
        t = current_theme()
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg=t["border"])
        inner = tk.Frame(popup, bg=t["panel_bg"], padx=12, pady=8)
        inner.pack(padx=1, pady=1)
        tk.Label(inner, text="Initial Built-In Test", font=FONT_BOLD,
                 bg=t["panel_bg"], fg=t["fg"]).pack(anchor="w", pady=(0, 6))
        for name, (ok, detail, ms) in self._ibit_results.items():
            row = tk.Frame(inner, bg=t["panel_bg"])
            row.pack(fill=tk.X, pady=1)
            icon = "\u2714" if ok else "\u2718"
            color = t["green"] if ok else t["red"]
            tk.Label(row, text="{} {}".format(icon, name),
                     font=FONT_SMALL, bg=t["panel_bg"], fg=color,
                     width=18, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=detail, font=FONT_SMALL,
                     bg=t["panel_bg"], fg=t["fg"],
                     anchor=tk.W).pack(side=tk.LEFT, padx=(4, 0))
            tk.Label(row, text="{}ms".format(ms), font=FONT_SMALL,
                     bg=t["panel_bg"], fg=t["gray"]
                     ).pack(side=tk.RIGHT)
        total_ms = sum(v[2] for v in self._ibit_results.values())
        tk.Label(inner, text="Total: {}ms".format(total_ms),
                 font=FONT_SMALL, bg=t["panel_bg"], fg=t["gray"]
                 ).pack(anchor="e", pady=(6, 0))
        popup.update_idletasks()
        x = self._ibit_label.winfo_rootx()
        y = (self._ibit_label.winfo_rooty()
             + self._ibit_label.winfo_height() + 4)
        popup.geometry("+{}+{}".format(x, y))
        popup.bind("<Leave>", lambda e: popup.destroy())
        popup.bind("<FocusOut>", lambda e: popup.destroy())

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self, t):
        self.configure(bg=t["panel_bg"])
        self.question_entry.configure(
            bg=t["input_bg"], fg=t["input_fg"], insertbackground=t["fg"])
        self.answer_text.configure(
            bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], selectbackground=t["accent"])
        self._status_label.configure(bg=t["panel_bg"])
        self._metrics_label.configure(bg=t["panel_bg"])
        self._sources_toggle_btn.configure(bg=t["panel_bg"], fg=t["accent"])

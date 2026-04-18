"""Settings panel. It shows important runtime settings and lets the operator verify how the app is configured."""
# ============================================================================
# HybridRAG V2 -- Settings Panel (src/gui/panels/settings_panel.py)
# ============================================================================
# Simplified settings view. Shows current configuration values:
#   - Retrieval: top_k, min_score, candidate_pool
#   - Reranker: enabled/disabled, top_n
#   - CRAG: enabled/disabled, confidence threshold, max retries
#   - LLM: model, provider, context window, temperature
#   - Paths: lance_db, entity_db
# All read-only display of current config. No mode switching.
# ============================================================================

import tkinter as tk
from tkinter import messagebox, ttk
import logging

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_SECTION, FONT_MONO, FONT_SMALL
from src.gui.scrollable import ScrollableFrame

logger = logging.getLogger(__name__)


class SettingsPanel(tk.LabelFrame):
    """Read-only display of current V2 configuration.

    Shows retrieval params, reranker toggle, CRAG toggle, LLM config,
    and file paths. No editing -- config changes require editing
    config/config.yaml and restarting.
    """

    def __init__(self, parent, model):
        t = current_theme()
        super().__init__(parent, text="Settings", padx=16, pady=16,
                         bg=t["panel_bg"], fg=t["accent"], font=FONT_BOLD)
        self._model = model
        self._config = model.config if model else None
        self._labels = []  # Track labels for theme updates
        self._build_widgets(t)

    def _build_widgets(self, t):
        """Build the settings display."""
        sf = ScrollableFrame(self, bg=t["panel_bg"])
        sf.pack(fill=tk.BOTH, expand=True)
        self._scrollable = sf
        inner = sf.inner

        cfg = self._config

        # -- Retrieval Section --
        self._add_section(inner, t, "Retrieval")
        if cfg and hasattr(cfg, "retrieval"):
            r = cfg.retrieval
            self._add_row(inner, t, "Top-K", str(r.top_k))
            self._add_row(inner, t, "Candidate Pool", str(r.candidate_pool))
            self._add_row(inner, t, "Min Score", str(r.min_score))
            self._add_row(inner, t, "Reranker Enabled",
                          "Yes" if r.reranker_enabled else "No")
            self._add_row(inner, t, "Reranker Top-N", str(r.reranker_top_n))
        else:
            self._add_row(inner, t, "Status", "Config not loaded")

        self._add_separator(inner, t)

        # -- CRAG Section --
        self._add_section(inner, t, "Corrective RAG (CRAG)")
        if cfg and hasattr(cfg, "crag"):
            c = cfg.crag
            self._add_row(inner, t, "Enabled", "Yes" if c.enabled else "No")
            self._add_row(inner, t, "Confidence Threshold",
                          str(c.confidence_threshold))
            self._add_row(inner, t, "Max Retries", str(c.max_retries))
            self._add_row(inner, t, "Verifier Model", c.verifier_model)
        else:
            self._add_row(inner, t, "Status", "CRAG not configured")

        self._add_separator(inner, t)

        # -- LLM Section --
        self._add_section(inner, t, "LLM Configuration")
        if cfg and hasattr(cfg, "llm"):
            llm = cfg.llm

            # Model selector dropdown
            model_row = tk.Frame(inner, bg=t["panel_bg"])
            model_row.pack(fill=tk.X, pady=2)
            tk.Label(
                model_row, text="Model:", font=FONT,
                bg=t["panel_bg"], fg=t["label_fg"], width=22, anchor=tk.W,
            ).pack(side=tk.LEFT)

            self._model_var = tk.StringVar(value=self._current_model_label(llm))
            self._model_dropdown = ttk.Combobox(
                model_row,
                textvariable=self._model_var,
                values=["GPT-4o", "phi4:14b"],
                state="readonly",
                width=20,
                font=FONT,
            )
            self._model_dropdown.pack(side=tk.LEFT)
            self._model_dropdown.bind("<<ComboboxSelected>>", self._on_model_change)

            self._model_status = tk.Label(
                model_row, text="", font=FONT_SMALL,
                bg=t["panel_bg"], fg=t["gray"],
            )
            self._model_status.pack(side=tk.LEFT, padx=(8, 0))

            self._add_row(inner, t, "Provider", llm.provider)
            self._add_row(inner, t, "Deployment", llm.deployment)
            self._add_row(inner, t, "Context Window",
                          "{:,}".format(llm.context_window))
            self._add_row(inner, t, "Max Tokens",
                          "{:,}".format(llm.max_tokens))
            self._add_row(inner, t, "Temperature", str(llm.temperature))
            self._add_row(inner, t, "Timeout",
                          "{}s".format(llm.timeout_seconds))
            if llm.api_base:
                self._add_row(inner, t, "API Base", llm.api_base)
        else:
            self._add_row(inner, t, "Status", "LLM not configured")

        self._add_separator(inner, t)

        # -- Extraction Section --
        self._add_section(inner, t, "Entity Extraction")
        if cfg and hasattr(cfg, "extraction"):
            ex = cfg.extraction
            self._add_row(inner, t, "Min Confidence",
                          str(ex.min_confidence))
            self._add_row(inner, t, "GLiNER Enabled",
                          "Yes" if ex.gliner_enabled else "No")
            self._add_row(inner, t, "GPT-4o Extraction",
                          "Yes" if ex.gpt4o_extraction else "No")
            self._add_row(inner, t, "Part Patterns",
                          str(len(ex.part_patterns)))
        else:
            self._add_row(inner, t, "Status", "Extraction not configured")

        self._add_separator(inner, t)

        # -- Paths Section --
        self._add_section(inner, t, "File Paths")
        if cfg and hasattr(cfg, "paths"):
            p = cfg.paths
            self._add_row(inner, t, "LanceDB", p.lance_db)
            self._add_row(inner, t, "Entity DB", p.entity_db)
            self._add_row(inner, t, "Corpus Source", p.embedengine_output)
            self._add_row(inner, t, "Site Vocabulary", p.site_vocabulary)
        else:
            self._add_row(inner, t, "Status", "Paths not configured")

        self._add_separator(inner, t)

        # -- Hardware Section --
        self._add_section(inner, t, "Hardware")
        if cfg:
            self._add_row(inner, t, "Preset",
                          getattr(cfg, "hardware_preset", "unknown"))
        else:
            self._add_row(inner, t, "Status", "Config not loaded")

        # -- Refresh button --
        btn_frame = tk.Frame(inner, bg=t["panel_bg"])
        btn_frame.pack(fill=tk.X, pady=(16, 8))

        self._refresh_btn = tk.Button(
            btn_frame, text="Refresh Counts", command=self._on_refresh,
            font=FONT, bg=t["accent"], fg=t["accent_fg"],
            relief=tk.FLAT, bd=0, padx=16, pady=6,
        )
        self._refresh_btn.pack(side=tk.LEFT)

        self._health_btn = tk.Button(
            btn_frame, text="Check Store Health", command=self._on_health_check,
            font=FONT, bg=t["input_bg"], fg=t["fg"],
            relief=tk.FLAT, bd=0, padx=16, pady=6,
        )
        self._health_btn.pack(side=tk.LEFT, padx=(8, 0))

        self._counts_label = tk.Label(
            btn_frame, text="", font=FONT_MONO,
            bg=t["panel_bg"], fg=t["gray"],
        )
        self._counts_label.pack(side=tk.LEFT, padx=(12, 0))

    # ------------------------------------------------------------------
    # Model selector
    # ------------------------------------------------------------------

    _MODEL_MAP = {
        "GPT-4o": {"model": "gpt-4o", "deployment": "gpt-4o", "provider": "auto"},
        "phi4:14b": {"model": "phi4:14b", "deployment": "", "provider": "ollama"},
    }

    def _current_model_label(self, llm) -> str:
        if llm.provider == "ollama" or "phi4" in llm.model:
            return "phi4:14b"
        return "GPT-4o"

    def _on_model_change(self, event=None):
        label = self._model_var.get()
        mapping = self._MODEL_MAP.get(label)
        if not mapping or not self._config:
            return

        self._config.llm.model = mapping["model"]
        self._config.llm.deployment = mapping["deployment"]
        self._config.llm.provider = mapping["provider"]

        try:
            self._save_provider_to_config(mapping)
            status = "Saved"
        except Exception as e:
            logger.warning("Failed to save model config: %s", e)
            status = "Save failed"

        self._model_status.config(text=status)
        logger.info("Model switched to %s (provider=%s)", label, mapping["provider"])

    def _save_provider_to_config(self, mapping):
        from pathlib import Path
        import yaml
        config_path = Path(__file__).resolve().parents[3] / "config" / "config.yaml"
        if not config_path.exists():
            return
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if "llm" not in raw:
            raw["llm"] = {}
        raw["llm"]["model"] = mapping["model"]
        raw["llm"]["deployment"] = mapping["deployment"]
        raw["llm"]["provider"] = mapping["provider"]
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # ------------------------------------------------------------------
    # Widget builders
    # ------------------------------------------------------------------

    def _add_section(self, parent, t, title):
        """Add a section header."""
        lbl = tk.Label(
            parent, text=title, font=FONT_SECTION,
            bg=t["panel_bg"], fg=t["accent"], anchor=tk.W,
        )
        lbl.pack(fill=tk.X, pady=(12, 4))
        self._labels.append(lbl)

    def _add_row(self, parent, t, label, value):
        """Add a key-value row."""
        row = tk.Frame(parent, bg=t["panel_bg"])
        row.pack(fill=tk.X, pady=2)

        key_lbl = tk.Label(
            row, text="{}:".format(label), font=FONT,
            bg=t["panel_bg"], fg=t["label_fg"], width=22, anchor=tk.W,
        )
        key_lbl.pack(side=tk.LEFT)

        val_lbl = tk.Label(
            row, text=value, font=FONT_MONO,
            bg=t["panel_bg"], fg=t["fg"], anchor=tk.W,
        )
        val_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._labels.extend([key_lbl, val_lbl])

    def _add_separator(self, parent, t):
        """Add a thin horizontal separator."""
        sep = tk.Frame(parent, height=1, bg=t["separator"])
        sep.pack(fill=tk.X, pady=8)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _on_refresh(self):
        """Refresh store counts and display them."""
        if self._model:
            self._model.refresh_counts()
            self._counts_label.config(
                text="Chunks: {:,} | Entities: {:,} | Rels: {:,}".format(
                    self._model.chunk_count,
                    self._model.entity_count,
                    self._model.relationship_count,
                )
            )

    def _on_health_check(self):
        """Show the current store health for the configured retrieval path."""
        if not self._model or not self._model.lance_store:
            messagebox.showwarning("Store Health", "LanceDB store is not initialized yet.")
            return

        lance_store = self._model.lance_store
        fts_status = lance_store.fts_status()
        vector_present = lance_store.has_vector_index()
        vector_ready = lance_store.vector_index_ready()
        vector_stats = lance_store.vector_index_stats()

        if vector_present:
            vector_text = "ready" if vector_ready else ("stale" if vector_ready is False else "present")
            indexed = vector_stats.get("num_indexed_rows")
            unindexed = vector_stats.get("num_unindexed_rows")
            if indexed is not None or unindexed is not None:
                vector_text += f" ({indexed or 0} indexed, {unindexed or 0} unindexed)"
        else:
            vector_text = "absent"

        fts_state = fts_status.get("state") or ("ready" if fts_status.get("ready") else "missing")
        if fts_status.get("ready"):
            fts_text = f"ready (probe={fts_status.get('probe_term')})"
        elif fts_state == "index_present":
            fts_text = f"present, probe failed ({fts_status.get('error') or 'FTS probe failed'})"
        else:
            fts_text = f"missing/unreadable ({fts_status.get('error') or 'FTS probe failed'})"

        summary = "\n".join([
            f"LanceDB: {lance_store.db_path}",
            f"Chunks: {self._model.chunk_count:,}",
            f"Vector index: {vector_text}",
            f"FTS: {fts_text}",
            f"Entities: {self._model.entity_count:,}",
            f"Relationships: {self._model.relationship_count:,}",
        ])

        self._counts_label.config(
            text=f"FTS: {'ready' if fts_status.get('ready') else ('present' if fts_state == 'index_present' else 'missing')} | Vector: {vector_text}"
        )

        if fts_status.get("ready") and vector_present:
            messagebox.showinfo("Store Health", summary)
        else:
            messagebox.showwarning("Store Health", summary)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self, t):
        """Re-apply theme colors."""
        self.configure(bg=t["panel_bg"], fg=t["accent"])
        if hasattr(self, "_scrollable"):
            self._scrollable.apply_theme(t)

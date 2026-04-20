"""Status bar. It gives a constant at-a-glance summary of system readiness at the bottom of the window."""
# ============================================================================
# HybridRAG V2 -- Status Bar (src/gui/panels/status_bar.py)
# ============================================================================
# Bottom status bar showing: live startup/readiness state, chunks loaded,
# FTS readiness, entities loaded, LLM status, and query path of last query.
# Refreshes every second so long cold boots remain understandable.
# ============================================================================

import tkinter as tk
import threading
import logging

from src.gui.helpers.safe_after import safe_after
from src.gui.theme import current_theme, FONT

logger = logging.getLogger(__name__)


class StatusBar(tk.Frame):
    """Bottom status bar with system health indicators.

    Displays:
      - Startup/readiness phase for cold boot
      - Chunks loaded (from LanceDB)
      - FTS readiness for the configured LanceDB store
      - Entities loaded (from EntityStore)
      - LLM status (available / not configured)
      - Last query path (SEMANTIC/ENTITY/AGGREGATE/TABULAR/COMPLEX)
    """

    REFRESH_MS = 1000  # 1 second

    def __init__(self, parent, model=None):
        t = current_theme()
        super().__init__(parent, relief=tk.FLAT, bd=1, bg=t["panel_bg"])
        self._model = model
        self._stop_event = threading.Event()
        self._refresh_timer_id = None
        self._last_query_path = ""
        self._llm_verified = False
        self._llm_verify_detail = ""
        self._llm_verify_running = False
        self._llm_client_seen = None
        self._observer_model = None

        self._build_widgets(t)
        self._bind_model(model)
        self._schedule_refresh()

    def _build_widgets(self, t):
        """Build all status indicator widgets."""
        # -- Startup / readiness indicator --
        self.startup_label = tk.Label(
            self, text="Startup: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["orange"], font=FONT,
        )
        self.startup_label.pack(side=tk.LEFT)

        self._sep0 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep0.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- Chunks indicator --
        self.chunks_label = tk.Label(
            self, text="Chunks: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["fg"], font=FONT,
        )
        self.chunks_label.pack(side=tk.LEFT)

        self._sep1 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep1.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- FTS indicator --
        self.fts_label = tk.Label(
            self, text="FTS: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.fts_label.pack(side=tk.LEFT)

        self._sep_fts = tk.Frame(self, width=1, bg=t["separator"])
        self._sep_fts.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- Entities indicator --
        self.entities_label = tk.Label(
            self, text="Entities: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["fg"], font=FONT,
        )
        self.entities_label.pack(side=tk.LEFT)

        self._sep2 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep2.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- LLM status indicator --
        self.llm_label = tk.Label(
            self, text="LLM: checking...", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.llm_label.pack(side=tk.LEFT)

        self._sep3 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep3.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- IBIT button --
        self.ibit_btn = tk.Button(
            self, text="Run IBIT", command=self._on_ibit,
            font=FONT, bg=t["input_bg"], fg=t["fg"],
            relief=tk.FLAT, bd=0, padx=8, pady=2,
        )
        self.ibit_btn.pack(side=tk.RIGHT, padx=(4, 8))

        # -- IBIT badge --
        self.ibit_label = tk.Label(
            self, text="IBIT: --", anchor=tk.E,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.ibit_label.pack(side=tk.RIGHT)

        self._sep_ibit = tk.Frame(self, width=1, bg=t["separator"])
        self._sep_ibit.pack(side=tk.RIGHT, fill=tk.Y, padx=8, pady=4)

        # -- Query path indicator (right-aligned) --
        self.path_label = tk.Label(
            self, text="Path: --", anchor=tk.E,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.path_label.pack(side=tk.RIGHT)

    def set_model(self, model):
        """Attach or replace the GUIModel reference."""
        self._model = model
        self._bind_model(model)
        self._refresh_status()

    def _bind_model(self, model):
        """Subscribe once to model state changes."""
        if model is None or model is self._observer_model:
            return
        try:
            model.on_state_change(self._on_model_state_change)
            self._observer_model = model
        except Exception as exc:
            logger.debug("Status bar failed to bind model observer: %s", exc)

    def _on_model_state_change(self):
        """Handle model updates from any thread."""
        safe_after(self, 0, self._refresh_status)

    def _format_startup_text(self, boot):
        """Format the boot banner shown at the left side of the status bar."""
        def _clip(text):
            return text if len(text) <= 78 else text[:75] + "..."

        status = boot.get("status") or "starting"
        phase = boot.get("phase_label") or "Starting GUI"
        detail = (boot.get("detail") or "").strip()
        elapsed = boot.get("elapsed_seconds") or 0.0
        seconds = "{:.0f}s".format(elapsed)

        if status == "starting":
            return _clip("Startup: {} ({})".format(phase, seconds))
        if status == "ready":
            return _clip("Ready: {} ({})".format(detail or "Ask is enabled.", seconds))
        if status == "degraded":
            return _clip("Degraded: {} ({})".format(
                detail or "Query surface is partially available.",
                seconds,
            ))
        if status == "failed":
            return _clip("Failed: {} ({})".format(
                detail or "Query pipeline is unavailable.",
                seconds,
            ))
        return _clip("Startup: {}".format(phase))

    def _startup_color(self, status, theme):
        if status == "ready":
            return theme["green"]
        if status == "failed":
            return theme["red"]
        return theme["orange"]

    def _reset_llm_verification_if_needed(self, llm_client):
        """Reset verification cache when the attached LLM client changes."""
        seen = id(llm_client) if llm_client is not None else None
        if seen != self._llm_client_seen:
            self._llm_client_seen = seen
            self._llm_verified = False
            self._llm_verify_detail = ""
            self._llm_verify_running = False

    def set_query_path(self, path_name: str):
        """Update the last query path display."""
        t = current_theme()
        self._last_query_path = path_name

        # Color-code the query path
        color_map = {
            "SEMANTIC": t["accent"],
            "ENTITY": t["green"],
            "AGGREGATE": t["orange"],
            "TABULAR": t["orange"],
            "COMPLEX": t["red"],
        }
        color = color_map.get(path_name, t["fg"])
        self.path_label.config(text="Path: {}".format(path_name), fg=color)

    def _schedule_refresh(self):
        """Schedule next status refresh."""
        if not self._stop_event.is_set():
            self._refresh_status()
            self._refresh_timer_id = self.after(
                self.REFRESH_MS, self._schedule_refresh
            )

    def _refresh_status(self):
        """Update all status indicators from current model state."""
        t = current_theme()
        try:
            if self._model is None:
                self.startup_label.config(text="Startup: --", fg=t["gray"])
                self.chunks_label.config(text="Chunks: --", fg=t["gray"])
                self.fts_label.config(text="FTS: --", fg=t["gray"])
                self.entities_label.config(text="Entities: --", fg=t["gray"])
                self.llm_label.config(text="LLM: not initialized", fg=t["gray"])
                return

            boot = self._model.get_boot_state_snapshot()
            boot_status = boot.get("status") or "starting"
            self.startup_label.config(
                text=self._format_startup_text(boot),
                fg=self._startup_color(boot_status, t),
            )

            # Chunks
            if self._model.lance_store is None and boot_status == "starting":
                self.chunks_label.config(text="Chunks: loading...", fg=t["orange"])
            elif self._model.lance_store is None and boot_status in ("degraded", "failed"):
                self.chunks_label.config(text="Chunks: unavailable", fg=t["red"])
            else:
                count = self._model.chunk_count
                self.chunks_label.config(
                    text="Chunks: {:,}".format(count),
                    fg=t["green"] if count > 0 else t["gray"],
                )

            # FTS readiness — honest 3-state: ready / warming up / not ready
            if self._model.lance_store is None and boot_status == "starting":
                self.fts_label.config(text="FTS: waiting for LanceDB...", fg=t["orange"])
            elif self._model.lance_store is None and boot_status in ("degraded", "failed"):
                self.fts_label.config(text="FTS: unavailable", fg=t["red"])
            elif self._model.fts_ready is True:
                self.fts_label.config(text="FTS: ready", fg=t["green"])
            elif self._model.fts_ready is None:
                # Still initializing — hasn't been checked yet
                self.fts_label.config(text="FTS: warming up...", fg=t["orange"])
            elif self._model.fts_ready is False:
                state = getattr(self._model, "fts_state", "")
                if state == "index_present":
                    # Index exists but probe failed — rebuilding
                    self.fts_label.config(text="FTS: rebuilding index...", fg=t["orange"])
                elif state == "not checked":
                    self.fts_label.config(text="FTS: warming up...", fg=t["orange"])
                else:
                    # Genuinely missing or broken
                    self.fts_label.config(text="FTS: NOT READY", fg=t["red"])

            # Entities + health warning when stores are empty
            ent_count = self._model.entity_count
            rel_count = self._model.relationship_count
            tbl_count = getattr(self._model, "table_count", 0) or 0
            if (
                self._model.entity_store is None
                and self._model.relationship_store is None
                and boot_status == "starting"
            ):
                self.entities_label.config(text="Entities: loading...", fg=t["orange"])
            elif self._model.entity_store is None and boot_status in ("degraded", "failed"):
                self.entities_label.config(text="Entities: unavailable", fg=t["orange"])
            elif self._model.relationship_store is None and boot_status in ("degraded", "failed"):
                self.entities_label.config(
                    text="Entities: {:,} | Rels: unavailable".format(ent_count),
                    fg=t["orange"],
                )
            elif rel_count == 0 and tbl_count == 0:
                self.entities_label.config(
                    text="Entities: {:,} | Rels: 0 | Tables: 0 [EMPTY - run extraction]".format(ent_count),
                    fg=t["red"],
                )
            elif rel_count == 0:
                self.entities_label.config(
                    text="Entities: {:,} | Rels: 0 [no relationships]".format(ent_count),
                    fg=t["orange"],
                )
            else:
                self.entities_label.config(
                    text="Entities: {:,} | Rels: {:,}".format(ent_count, rel_count),
                    fg=t["green"] if ent_count > 0 else t["gray"],
                )

            # LLM — show VERIFIED connection status (not just "client exists")
            llm_client = getattr(self._model, "_llm_client", None)
            self._reset_llm_verification_if_needed(llm_client)
            if self._llm_verified:
                self.llm_label.config(
                    text=self._llm_verify_detail, fg=t["green"],
                )
            elif llm_client is None and boot_status == "starting":
                self.llm_label.config(text="LLM: initializing...", fg=t["orange"])
            elif llm_client is None and boot_status == "degraded":
                self.llm_label.config(text="LLM: unavailable", fg=t["orange"])
            elif llm_client and getattr(llm_client, "available", False):
                if not self._llm_verify_running:
                    self._llm_verify_running = True
                    self.llm_label.config(
                        text="LLM: verifying connection...", fg=t["orange"],
                    )
                    self._verify_llm_connection(llm_client)
                else:
                    self.llm_label.config(
                        text="LLM: verifying connection...", fg=t["orange"],
                    )
            else:
                self.llm_label.config(text="LLM: NOT CONNECTED", fg=t["red"])

        except Exception as e:
            logger.debug("Status bar refresh error: %s", e)

    def _verify_llm_connection(self, llm_client):
        """Run a real API probe in a background thread. Sets _llm_verified on result."""
        def _probe():
            try:
                provider = getattr(llm_client, "_provider", "unknown")
                model = getattr(llm_client, "model", "unknown")
                response = llm_client.call("Say OK", max_tokens=5)
                if response and response.text:
                    self._llm_verified = True
                    if provider == "ollama":
                        self._llm_verify_detail = "LLM: {} (local, verified)".format(model)
                    else:
                        self._llm_verify_detail = "LLM: {} (online, verified)".format(model)
                    logger.info("LLM connection verified: %s (%s)", model, provider)
                else:
                    self._llm_verified = False
                    self._llm_verify_detail = ""
                    logger.warning("LLM probe returned empty response")
            except Exception as e:
                self._llm_verified = False
                self._llm_verify_detail = ""
                logger.warning("LLM connection verification failed: %s", e)
            finally:
                self._llm_verify_running = False
                safe_after(self, 0, self._refresh_status)

        threading.Thread(target=_probe, daemon=True).start()

    def _on_ibit(self):
        """Run IBIT and display results."""
        if not self._model:
            self.ibit_label.config(text="IBIT: no model", fg=current_theme()["red"])
            return

        t = current_theme()
        self.ibit_label.config(text="IBIT: running...", fg=t["orange"])
        self.ibit_btn.config(state=tk.DISABLED)
        self.update_idletasks()

        def _run():
            try:
                results = self._model.run_ibit()
                passed = sum(1 for v in results.values() if v[0])
                total = len(results)
                total_ms = sum(v[2] for v in results.values())

                if passed == total:
                    badge = "IBIT: {}/{} PASS".format(passed, total)
                    color = t["green"]
                else:
                    badge = "IBIT: {}/{} FAIL".format(passed, total)
                    color = t["red"]

                def _update():
                    self.ibit_label.config(text=badge, fg=color)
                    self.ibit_btn.config(state=tk.NORMAL)
                    self._show_ibit_detail(results, total_ms)

                safe_after(self, 0, _update)
            except Exception as e:
                def _error():
                    self.ibit_label.config(
                        text="IBIT: ERROR", fg=t["red"],
                    )
                    self.ibit_btn.config(state=tk.NORMAL)
                safe_after(self, 0, _error)

        threading.Thread(target=_run, daemon=True).start()

    def _show_ibit_detail(self, results, total_ms):
        """Show IBIT detail popup (auto-closes after 10s)."""
        t = current_theme()
        popup = tk.Toplevel(self)
        popup.title("IBIT Results")
        popup.geometry("500x300")
        popup.configure(bg=t["panel_bg"])

        header = tk.Label(
            popup, text="Built-In Test Results ({:,}ms)".format(total_ms),
            font=("Segoe UI", 12, "bold"), bg=t["panel_bg"], fg=t["accent"],
        )
        header.pack(padx=16, pady=(12, 8))

        for name, (passed, detail, elapsed) in results.items():
            row = tk.Frame(popup, bg=t["panel_bg"])
            row.pack(fill=tk.X, padx=16, pady=2)

            tag = "[PASS]" if passed else "[FAIL]"
            tag_color = t["green"] if passed else t["red"]

            tk.Label(
                row, text=tag, font=("Segoe UI", 10, "bold"),
                bg=t["panel_bg"], fg=tag_color, width=7, anchor=tk.W,
            ).pack(side=tk.LEFT)

            tk.Label(
                row, text="{}: {} ({}ms)".format(name, detail, elapsed),
                font=("Segoe UI", 10), bg=t["panel_bg"], fg=t["fg"],
                anchor=tk.W,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            popup, text="Close", command=popup.destroy,
            font=FONT, bg=t["accent"], fg=t["accent_fg"],
            relief=tk.FLAT, padx=16, pady=4,
        ).pack(pady=(12, 8))

        popup.after(10000, popup.destroy)

    def apply_theme(self, t):
        """Re-apply theme colors to all widgets."""
        self.configure(bg=t["panel_bg"])
        for w in (self.startup_label, self.chunks_label, self.fts_label, self.entities_label,
                  self.llm_label, self.path_label, self.ibit_label):
            w.configure(bg=t["panel_bg"])
        for sep in (self._sep0, self._sep1, self._sep_fts, self._sep2, self._sep3, self._sep_ibit):
            sep.configure(bg=t["separator"])
        self._refresh_status()

    def force_refresh(self):
        """Immediately refresh all indicators."""
        if self._model:
            self._model.refresh_counts()
        self._refresh_status()

    def stop(self):
        """Stop the periodic refresh timer."""
        self._stop_event.set()
        if self._refresh_timer_id is not None:
            try:
                self.after_cancel(self._refresh_timer_id)
            except Exception:
                pass
            self._refresh_timer_id = None

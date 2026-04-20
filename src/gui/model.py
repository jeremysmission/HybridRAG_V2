"""GUI model layer. It exposes query state and store counts in a form that panels can observe."""
# ============================================================================
# HybridRAG V2 -- GUI Model Layer (src/gui/model.py)
# ============================================================================
# Thin observable wrapper around QueryPipeline for the GUI.
# Pure Python -- no tkinter imports. Enables unit testing without a display.
#
# Properties: is_querying, last_response, chunk_count, entity_count,
#             relationship_count, llm_available
# Methods:    query(text, top_k, callback) -- background thread
# Observer:   on_state_change(callback) -- views subscribe here
# ============================================================================

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GUIModel:
    """Observable model that wraps the V2 QueryPipeline for GUI consumption.

    All state mutations fire on_state_change callbacks so views can
    update without polling.  query() runs the pipeline in a background
    thread and delivers the result via callback.

    Attributes:
        is_querying: True while a background query is in progress.
        last_response: The most recent QueryResponse, or None.
        chunk_count: Number of chunks in the vector store.
        entity_count: Number of entities in the entity store.
        relationship_count: Number of relationships in the relationship store.
        llm_available: Whether the LLM client is configured and reachable.
    """

    def __init__(
        self,
        pipeline=None,
        lance_store=None,
        entity_store=None,
        relationship_store=None,
        llm_client=None,
        config=None,
        boot_started_at: Optional[float] = None,
    ):
        self._pipeline = pipeline
        self._lance_store = lance_store
        self._entity_store = entity_store
        self._relationship_store = relationship_store
        self._llm_client = llm_client
        self._config = config

        # Observable state
        self.is_querying: bool = False
        self.last_response = None
        self.chunk_count: int = 0
        self.entity_count: int = 0
        self.relationship_count: int = 0
        self.table_count: int = 0
        self.llm_available: bool = False
        self.fts_ready: Optional[bool] = None
        self.fts_state: str = "not checked"
        self.fts_status_detail: str = "not checked"
        self.boot_status: str = "starting"
        self.boot_phase_key: str = "startup"
        self.boot_phase_label: str = "Starting GUI"
        self.boot_detail: str = "Window opened. Backend initialization pending."
        self.boot_issues: list[str] = []
        self.boot_started_at: float = (
            float(boot_started_at)
            if boot_started_at is not None
            else time.perf_counter()
        )
        self.boot_finished_at: Optional[float] = None

        # Observer list
        self._observers: list[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

        # Refresh store counts on init
        self.refresh_counts()
        self._check_llm()

    # ------------------------------------------------------------------
    # Observer pattern
    # ------------------------------------------------------------------

    def on_state_change(self, callback: Callable[[], None]) -> None:
        """Subscribe to state changes. Callback is called with no args."""
        with self._lock:
            self._observers.append(callback)

    def _notify(self) -> None:
        """Notify all observers of a state change."""
        with self._lock:
            observers = list(self._observers)
        for cb in observers:
            try:
                cb()
            except Exception as exc:
                logger.debug("Observer callback failed: %s", exc)

    # ------------------------------------------------------------------
    # Store counts
    # ------------------------------------------------------------------

    def refresh_counts(self, notify: bool = True) -> None:
        """Refresh chunk/entity/relationship counts from stores."""
        try:
            self.chunk_count = self._lance_store.count() if self._lance_store else 0
        except Exception:
            self.chunk_count = 0
        self._refresh_lance_health()

        try:
            self.entity_count = self._entity_store.count_entities() if self._entity_store else 0
        except Exception:
            self.entity_count = 0

        try:
            self.relationship_count = (
                self._relationship_store.count() if self._relationship_store else 0
            )
        except Exception:
            self.relationship_count = 0

        try:
            self.table_count = (
                self._entity_store.count_table_rows() if self._entity_store else 0
            )
        except Exception:
            self.table_count = 0

        if notify:
            self._notify()

    def _refresh_lance_health(self) -> None:
        """Refresh FTS readiness for the attached LanceDB store."""
        if self._lance_store is None:
            self.fts_ready = None
            self.fts_state = "unavailable"
            self.fts_status_detail = "store not initialized"
            return
        try:
            status = self._lance_store.fts_status()
            self.fts_ready = bool(status.get("ready"))
            self.fts_state = str(status.get("state") or ("ready" if self.fts_ready else "missing"))
            if self.fts_ready:
                probe_term = status.get("probe_term") or "n/a"
                self.fts_status_detail = f"ready ({probe_term})"
            elif self.fts_state == "index_present":
                detail = status.get("error") or "FTS probe failed"
                self.fts_status_detail = f"index present ({detail})"
            else:
                detail = status.get("error") or "FTS probe failed"
                self.fts_status_detail = detail
        except Exception as exc:
            self.fts_ready = False
            self.fts_state = "error"
            self.fts_status_detail = str(exc)

    def _check_llm(self) -> None:
        """Check whether the LLM client appears configured."""
        try:
            if self._llm_client is not None:
                self.llm_available = bool(getattr(self._llm_client, "available", False))
            elif (
                self._pipeline is not None
                and getattr(self._pipeline, "generator", None) is not None
            ):
                generator_llm = getattr(self._pipeline.generator, "llm", None)
                self.llm_available = bool(getattr(generator_llm, "available", False))
            else:
                self.llm_available = False
        except Exception:
            self.llm_available = False

    # ------------------------------------------------------------------
    # Startup / readiness state
    # ------------------------------------------------------------------

    def attach_runtime(
        self,
        pipeline=None,
        lance_store=None,
        entity_store=None,
        relationship_store=None,
        llm_client=None,
        config=None,
    ) -> None:
        """Attach live backend objects after asynchronous startup finishes."""
        with self._lock:
            self._pipeline = pipeline
            self._lance_store = lance_store
            self._entity_store = entity_store
            self._relationship_store = relationship_store
            self._llm_client = llm_client
            self._config = config

        self.refresh_counts(notify=False)
        self._check_llm()
        self._notify()

    def set_pipeline(self, pipeline) -> None:
        """Attach the live query pipeline when the app is ready to query."""
        with self._lock:
            self._pipeline = pipeline
        self._check_llm()
        self._notify()

    def set_boot_phase(
        self,
        phase_key: str,
        phase_label: str,
        detail: str = "",
    ) -> None:
        """Record the current startup phase."""
        with self._lock:
            self.boot_status = "starting"
            self.boot_phase_key = phase_key
            self.boot_phase_label = phase_label
            self.boot_detail = detail
            self.boot_finished_at = None
        self._notify()

    def add_boot_issue(self, issue: str) -> None:
        """Record a startup warning or failure detail once."""
        issue = (issue or "").strip()
        if not issue:
            return
        with self._lock:
            if issue not in self.boot_issues:
                self.boot_issues.append(issue)

    def mark_boot_ready(self, detail: str = "") -> None:
        """Mark startup complete with a fully ready query surface."""
        with self._lock:
            self.boot_status = "ready"
            self.boot_phase_key = "ready"
            self.boot_phase_label = "Ready"
            self.boot_detail = detail
            self.boot_finished_at = time.perf_counter()
        self._notify()

    def mark_boot_degraded(self, detail: str = "") -> None:
        """Mark startup complete in a reduced-capability state."""
        with self._lock:
            self.boot_status = "degraded"
            self.boot_phase_key = "degraded"
            self.boot_phase_label = "Degraded"
            self.boot_detail = detail
            self.boot_finished_at = time.perf_counter()
        self._notify()

    def mark_boot_failed(self, detail: str = "") -> None:
        """Mark startup complete without a usable query pipeline."""
        with self._lock:
            self.boot_status = "failed"
            self.boot_phase_key = "failed"
            self.boot_phase_label = "Failed"
            self.boot_detail = detail
            self.boot_finished_at = time.perf_counter()
        self._notify()

    def get_boot_state_snapshot(self) -> dict[str, Any]:
        """Return a stable snapshot of startup state for GUI rendering."""
        with self._lock:
            started_at = self.boot_started_at
            finished_at = self.boot_finished_at
            phase_key = self.boot_phase_key
            phase_label = self.boot_phase_label
            status = self.boot_status
            detail = self.boot_detail
            issues = list(self.boot_issues)
            can_query = self._pipeline is not None

        elapsed = max(0.0, (finished_at or time.perf_counter()) - started_at)
        return {
            "status": status,
            "phase_key": phase_key,
            "phase_label": phase_label,
            "detail": detail,
            "issues": issues,
            "elapsed_seconds": elapsed,
            "can_query": can_query,
        }

    def run_ibit(self) -> dict:
        """Run a built-in test verifying all subsystems.

        Returns a dict of check_name -> (passed: bool, detail: str, elapsed_ms: int).
        Ported from V1 status_bar_ibit.py pattern.
        """
        import time
        results = {}

        # Check 1: LanceDB / Vector Store
        start = time.perf_counter()
        try:
            count = self._lance_store.count() if self._lance_store else 0
            passed = count > 0
            detail = "{:,} chunks".format(count) if passed else "empty or not loaded"
        except Exception as e:
            passed = False
            detail = str(e)[:60]
        results["Vector Store"] = (passed, detail, int((time.perf_counter() - start) * 1000))

        # Check 2: FTS Index
        start = time.perf_counter()
        try:
            fts_ok = self.fts_ready is True
            detail = self.fts_status_detail or ("ready" if fts_ok else "not ready")
        except Exception as e:
            fts_ok = False
            detail = str(e)[:60]
        results["FTS Index"] = (fts_ok, detail, int((time.perf_counter() - start) * 1000))

        # Check 3: Entity Store
        start = time.perf_counter()
        try:
            ent_count = self._entity_store.count_entities() if self._entity_store else 0
            passed = ent_count > 0
            detail = "{:,} entities".format(ent_count) if passed else "empty"
        except Exception as e:
            passed = False
            detail = str(e)[:60]
        results["Entity Store"] = (passed, detail, int((time.perf_counter() - start) * 1000))

        # Check 4: LLM Connection (live probe)
        start = time.perf_counter()
        try:
            client = self._llm_client
            if client and getattr(client, "available", False):
                provider = getattr(client, "_provider", "unknown")
                model = getattr(client, "model", "unknown")
                # Attempt a minimal API call to verify connection
                response = client.call("Say OK", max_tokens=5)
                if response and response.text:
                    passed = True
                    detail = "{} ({}) - verified".format(model, provider)
                else:
                    passed = False
                    detail = "{} ({}) - empty response".format(model, provider)
            else:
                passed = False
                detail = "LLM client not available"
        except Exception as e:
            passed = False
            detail = "Connection failed: {}".format(str(e)[:40])
        results["LLM Connection"] = (passed, detail, int((time.perf_counter() - start) * 1000))

        # Check 5: Embedder
        start = time.perf_counter()
        try:
            if self._pipeline and hasattr(self._pipeline, "vector_retriever"):
                vr = self._pipeline.vector_retriever
                embedder = getattr(vr, "embedder", None)
                if embedder and getattr(embedder, "_mode", "") in ("cuda", "onnx"):
                    passed = True
                    detail = "ready ({})".format(getattr(embedder, "_mode", ""))
                else:
                    passed = False
                    detail = "not initialized"
            else:
                passed = False
                detail = "pipeline not ready"
        except Exception as e:
            passed = False
            detail = str(e)[:60]
        results["Embedder"] = (passed, detail, int((time.perf_counter() - start) * 1000))

        logger.info("IBIT results: %s", {k: (v[0], v[1]) for k, v in results.items()})
        return results

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def query(
        self,
        text: str,
        top_k: int = 10,
        callback: Optional[Callable[[Any], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Run a query in a background thread.

        Args:
            text: The query string.
            top_k: Number of results to retrieve.
            callback: Called with the QueryResponse on success.
            error_callback: Called with the exception on failure.
        """
        if self._pipeline is None:
            if error_callback:
                error_callback(RuntimeError("Pipeline not initialized"))
            return

        self._cancel_event.clear()
        self.is_querying = True
        self._notify()

        def _run():
            try:
                if self._cancel_event.is_set():
                    return
                response = self._pipeline.query(text, top_k=top_k)
                if self._cancel_event.is_set():
                    return
                self.last_response = response
                self.is_querying = False
                self._notify()
                if callback:
                    callback(response)
            except Exception as exc:
                self.is_querying = False
                self._notify()
                logger.warning("Query failed: %s", exc)
                if error_callback:
                    error_callback(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def cancel_query(self) -> None:
        """Signal the current query to stop."""
        self._cancel_event.set()
        self.is_querying = False
        self._notify()

    # ------------------------------------------------------------------
    # Properties for direct store access (read-only)
    # ------------------------------------------------------------------

    @property
    def pipeline(self):
        return self._pipeline

    @property
    def entity_store(self):
        return self._entity_store

    @property
    def relationship_store(self):
        return self._relationship_store

    @property
    def lance_store(self):
        return self._lance_store

    @property
    def config(self):
        return self._config

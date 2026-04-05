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
        self.llm_available: bool = False

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

    def refresh_counts(self) -> None:
        """Refresh chunk/entity/relationship counts from stores."""
        try:
            self.chunk_count = self._lance_store.count() if self._lance_store else 0
        except Exception:
            self.chunk_count = 0

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

        self._notify()

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

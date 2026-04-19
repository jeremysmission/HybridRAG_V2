"""GUI launcher. It opens the desktop app quickly and finishes the heavy backend startup work in the background."""
# ============================================================================
# HybridRAG V2 -- GUI Launcher (src/gui/launch_gui.py)
# ============================================================================
# Entry point that boots the system and opens the GUI window.
# Three-phase launch:
#   Phase 1 - Load config (fast)
#   Phase 2 - Open GUI window immediately (user sees something)
#   Phase 3 - Initialize heavy backends in background thread
#             (embedder, LLM client, stores, pipeline)
#
# Graceful degradation: GUI boots even if LLM is unavailable.
# The status bar shows "not configured" and Ask button stays disabled
# until the pipeline is ready.
#
# Usage: python -m src.gui.launch_gui
#        or: python src/gui/launch_gui.py
# ============================================================================

import os
import sys
import logging
import threading
import time

# Ensure project root is on sys.path BEFORE any src.* imports
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _step(msg):
    """Print a startup step to console immediately (no logging dependency)."""
    ts = time.strftime("%H:%M:%S")
    print("[STARTUP {}] {}".format(ts, msg), flush=True)


def _sanitize_tk_env():
    """Auto-heal common Tk startup failures caused by bad environment vars."""
    from glob import glob

    for var, must_have in (
        ("TCL_LIBRARY", "init.tcl"),
        ("TK_LIBRARY", "tk.tcl"),
    ):
        val = os.environ.get(var)
        if not val:
            continue
        marker = os.path.join(val, must_have)
        if not (os.path.isdir(val) and os.path.isfile(marker)):
            _step("Tk env fix: clearing invalid {}={}".format(var, val))
            os.environ.pop(var, None)

    pyhome = os.environ.get("PYTHONHOME")
    if pyhome and not os.path.isdir(pyhome):
        _step("Tk env fix: clearing invalid PYTHONHOME={}".format(pyhome))
        os.environ.pop("PYTHONHOME", None)

    tcl_root = os.path.join(sys.base_prefix, "tcl")
    if os.path.isdir(tcl_root):
        if not os.environ.get("TCL_LIBRARY"):
            tcl_dirs = sorted(glob(os.path.join(tcl_root, "tcl*")))
            for d in tcl_dirs:
                if os.path.isfile(os.path.join(d, "init.tcl")):
                    os.environ["TCL_LIBRARY"] = d
                    break
        if not os.environ.get("TK_LIBRARY"):
            tk_dirs = sorted(glob(os.path.join(tcl_root, "tk*")))
            for d in tk_dirs:
                if os.path.isfile(os.path.join(d, "tk.tcl")):
                    os.environ["TK_LIBRARY"] = d
                    break


def _load_backends(app, config, logger):
    """Load heavy backends in a background thread, then attach to the GUI."""
    from src.gui.helpers.safe_after import safe_after

    pipeline = None
    lance_store = None
    entity_store = None
    relationship_store = None
    llm_client = None

    try:
        _step("Backend: loading config...")
        from src.config.schema import V2Config

        # -- Initialize stores --
        _step("Backend: opening LanceDB...")
        try:
            from src.store.lance_store import LanceStore
            lance_path = config.paths.lance_db
            # Resolve relative to project root
            if not os.path.isabs(lance_path):
                lance_path = os.path.join(_project_root, lance_path)
            lance_store = LanceStore(lance_path)
            chunk_count = lance_store.count()
            logger.info("[OK] LanceDB opened (%d chunks)", chunk_count)
            fts_status = lance_store.fts_status()
            if fts_status.get("ready"):
                logger.info(
                    "[OK] LanceDB FTS ready (probe=%s, path=%s)",
                    fts_status.get("probe_term"),
                    lance_path,
                )
            elif fts_status.get("state") == "index_present":
                logger.warning(
                    "[WARN] LanceDB FTS index present but probe failed at %s: %s",
                    lance_path,
                    fts_status.get("error") or "FTS probe failed",
                )
            else:
                logger.warning(
                    "[WARN] LanceDB FTS missing/unreadable at %s: %s. "
                    "Rebuild with scripts/import_embedengine.py --create-index "
                    "or LanceStore.create_fts_index().",
                    lance_path,
                    fts_status.get("error") or "FTS probe failed",
                )
        except Exception as exc:
            logger.warning("[WARN] LanceDB init failed: %s", exc)

        _step("Backend: opening EntityStore...")
        try:
            from src.store.entity_store import EntityStore
            entity_path = config.paths.entity_db
            if not os.path.isabs(entity_path):
                entity_path = os.path.join(_project_root, entity_path)
            entity_store = EntityStore(entity_path)
            logger.info("[OK] EntityStore opened (%d entities)",
                        entity_store.count_entities())
        except Exception as exc:
            logger.warning("[WARN] EntityStore init failed: %s", exc)

        _step("Backend: opening RelationshipStore...")
        try:
            from src.store.relationship_store import RelationshipStore
            rel_path = config.paths.entity_db
            if not os.path.isabs(rel_path):
                rel_path = os.path.join(_project_root, rel_path)
            relationship_store = RelationshipStore(rel_path)
            logger.info("[OK] RelationshipStore opened (%d relationships)",
                        relationship_store.count())
        except Exception as exc:
            logger.warning("[WARN] RelationshipStore init failed: %s", exc)

        # -- Entity store health check --
        # Coordinator directive 2026-04-16: warn if relationship and table stores
        # are empty, as this indicates the extraction pipeline hasn't populated
        # the stores that the entity retriever depends on. Empty stores cause
        # cascading LIKE scans on 19.9M rows (13-166s structured_lookup).
        try:
            _rel_count = relationship_store.count() if relationship_store else 0
            _tbl_count = entity_store.count_table_rows() if entity_store else 0
            _ent_count = entity_store.count_entities() if entity_store else 0
            if _rel_count == 0 and _tbl_count == 0:
                logger.warning(
                    "[WARN] Entity store health: relationships=%d, "
                    "extracted_tables=%d, entities=%d. The relationship and "
                    "table stores are EMPTY. Entity/aggregate queries will "
                    "fall back to slow LIKE scans. Run tiered_extract.py to "
                    "populate.",
                    _rel_count, _tbl_count, _ent_count,
                )
            elif _rel_count == 0:
                logger.warning(
                    "[WARN] Relationship store is empty (0 relationships). "
                    "Cross-document queries will not find relationship triples. "
                    "Run tiered_extract.py to populate.",
                )
        except Exception:
            pass  # Don't block startup for health-check failures

        # -- Initialize embedder --
        _step("Backend: initializing embedder...")
        embedder = None
        try:
            from src.query.embedder import Embedder
            embedder = Embedder(
                model_name="nomic-ai/nomic-embed-text-v1.5",
                dim=768,
                device="cuda",
            )
            logger.info("[OK] Embedder initialized (%s, dim=%d)", embedder.mode, embedder.dim)
        except Exception as exc:
            logger.warning("[WARN] Embedder init failed: %s", exc)

        # -- Initialize LLM client --
        _step("Backend: initializing LLM client...")
        try:
            from src.llm.client import LLMClient
            provider = config.llm.provider if config.llm.provider != "auto" else ""
            llm_client = LLMClient(
                api_base=config.llm.api_base,
                api_version=config.llm.api_version,
                model=config.llm.model,
                deployment=config.llm.deployment,
                max_tokens=config.llm.max_tokens,
                temperature=config.llm.temperature,
                timeout_seconds=config.llm.timeout_seconds,
                provider_override=provider,
            )
            logger.info("[OK] LLM client initialized (model=%s)", config.llm.model)
        except Exception as exc:
            logger.warning("[WARN] LLM client init failed: %s", exc)
            logger.warning("       GUI will run without LLM generation.")

        # -- Build query pipeline --
        _step("Backend: building query pipeline...")
        try:
            from src.query.query_router import QueryRouter
            from src.query.vector_retriever import VectorRetriever
            from src.query.entity_retriever import EntityRetriever
            from src.query.context_builder import ContextBuilder
            from src.query.generator import Generator
            from src.query.pipeline import QueryPipeline

            router = QueryRouter(llm_client) if llm_client else None
            vector_retriever = (
                VectorRetriever(
                    lance_store,
                    embedder,
                    top_k=config.retrieval.top_k,
                    candidate_pool=config.retrieval.candidate_pool,
                )
                if lance_store and embedder else None
            )
            entity_retriever = EntityRetriever(
                entity_store, relationship_store
            ) if entity_store and relationship_store else None
            context_builder = ContextBuilder(
                top_k=config.retrieval.top_k,
                reranker_enabled=config.retrieval.reranker_enabled,
            )
            generator = Generator(llm_client) if llm_client and llm_client.available else None

            # Aggregation executor is built unconditionally (does not require an
            # LLM). Logged so QA can verify the attach at boot time.
            aggregation_executor = None
            try:
                from src.query.aggregation_executor import build_default_executor
                aggregation_executor = build_default_executor(
                    data_dir=config.paths.lance_db,
                    aliases_yaml="config/canonical_aliases.yaml",
                )
                cov = aggregation_executor.store.coverage_summary()
                logger.info(
                    "[OK] Aggregation executor attached (failure_events=%d, with_system=%d)",
                    cov.get("total_events", 0), cov.get("with_system", 0),
                )
            except Exception as agg_exc:
                logger.warning("[WARN] Aggregation executor init failed: %s", agg_exc)

            # Pipeline assembles when core retrieval exists. Generator is
            # optional — aggregation queries work without an LLM (SAG pattern).
            if router and vector_retriever and context_builder:
                crag_verifier = None
                if config.crag.enabled and generator:
                    try:
                        from src.query.crag_verifier import CRAGVerifier
                        crag_verifier = CRAGVerifier(
                            config=config.crag,
                            llm_client=llm_client,
                            vector_retriever=vector_retriever,
                            context_builder=context_builder,
                            generator=generator,
                        )
                        logger.info("[OK] CRAG verifier enabled")
                    except Exception as crag_exc:
                        logger.warning("[WARN] CRAG init failed: %s", crag_exc)

                pipeline = QueryPipeline(
                    router=router,
                    vector_retriever=vector_retriever,
                    entity_retriever=entity_retriever,
                    context_builder=context_builder,
                    generator=generator,
                    crag_verifier=crag_verifier,
                    aggregation_executor=aggregation_executor,
                )
                if generator is None:
                    logger.info(
                        "[OK] Query pipeline assembled in aggregation-only mode (no LLM)"
                    )
                else:
                    logger.info("[OK] Query pipeline assembled")
            else:
                missing = []
                if not router:
                    missing.append("router")
                if not vector_retriever:
                    missing.append("vector_retriever")
                logger.warning(
                    "[WARN] Pipeline incomplete (missing: %s)",
                    ", ".join(missing),
                )
        except Exception as exc:
            logger.warning("[WARN] Pipeline assembly failed: %s", exc)

    except Exception as exc:
        logger.error("[ERROR] Backend loading failed: %s", exc)

    # Build GUIModel and attach to app on the main thread
    _step("Backend: attaching model to GUI...")
    from src.gui.model import GUIModel

    model = GUIModel(
        pipeline=pipeline,
        lance_store=lance_store,
        entity_store=entity_store,
        relationship_store=relationship_store,
        llm_client=llm_client,
        config=config,
    )

    def _attach():
        app.set_model(model)
        _step("Backend: model attached. GUI ready.")

    safe_after(app, 0, _attach)


def main():
    """Boot config, open GUI immediately, load backends in background."""
    _step("main() entered")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("gui_launcher")
    _sanitize_tk_env()

    # -- Phase 1: Load config --
    _step("Phase 1: load config...")
    config = None
    try:
        from src.config.schema import load_config, V2Config
        config_path = os.path.join(_project_root, "config", "config.yaml")
        config = load_config(config_path)
        _step("Phase 1 done (preset={})".format(config.hardware_preset))
    except Exception as exc:
        _step("Phase 1 FAILED: {}".format(exc))
        from src.config.schema import V2Config
        config = V2Config()

    # -- Phase 2: Open GUI immediately --
    _step("Phase 2: creating GUI window...")
    from src.gui.app import HybridRAGApp

    # Create a placeholder model so the GUI has something to reference
    from src.gui.model import GUIModel
    placeholder_model = GUIModel(config=config)

    app = HybridRAGApp(model=placeholder_model, config=config)
    _step("Phase 2 done: GUI window created")

    # -- Phase 3: Load backends in background --
    _step("Phase 3: starting backend thread...")
    backend_thread = threading.Thread(
        target=_load_backends,
        args=(app, config, logger),
        daemon=True,
    )
    backend_thread.start()
    _step("Phase 3: backend thread running")

    # -- Phase 4: Run the GUI event loop --
    _step("Phase 4: entering mainloop()")
    app.mainloop()
    _step("Phase 4: mainloop exited")


if __name__ == "__main__":
    main()

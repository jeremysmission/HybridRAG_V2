from __future__ import annotations

from types import SimpleNamespace

from src.cli import ask


def test_cli_ask_json_smoke(monkeypatch, capsys):
    class DummyPipeline:
        def query(self, query: str, top_k: int = 10):
            assert query == "top 5 failing parts in NEXION 2024"
            assert top_k == 7
            return SimpleNamespace(
                query_path="AGGREGATION_GREEN",
                confidence="GREEN",
                sources=["D:/CorpusTransfr/example.docx"],
                chunks_used=3,
                latency_ms=42,
                answer="stub answer",
            )

    class DummyStore:
        def close(self):
            return None

    runtime = SimpleNamespace(
        pipeline=DummyPipeline(),
        lance_store=DummyStore(),
        entity_store=DummyStore(),
        relationship_store=DummyStore(),
    )

    monkeypatch.setattr(ask, "boot_system", lambda config: runtime)
    monkeypatch.setattr(
        "sys.argv",
        ["ask.py", "top 5 failing parts in NEXION 2024", "--top-k", "7", "--json"],
    )

    rc = ask.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert '"query_path": "AGGREGATION_GREEN"' in out
    assert '"confidence": "GREEN"' in out


def test_cli_ask_human_readable(monkeypatch, capsys):
    class DummyPipeline:
        def query(self, query: str, top_k: int = 10):
            return SimpleNamespace(
                query_path="LOGISTICS_GUARD",
                confidence="NOT_SUPPORTED",
                sources=[],
                chunks_used=0,
                latency_ms=5,
                answer="guard answer",
            )

    class DummyStore:
        def close(self):
            return None

    runtime = SimpleNamespace(
        pipeline=DummyPipeline(),
        lance_store=DummyStore(),
        entity_store=DummyStore(),
        relationship_store=DummyStore(),
    )

    monkeypatch.setattr(ask, "boot_system", lambda config: runtime)
    monkeypatch.setattr("sys.argv", ["ask.py", "how many open POs are outstanding"])

    rc = ask.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "Path:       LOGISTICS_GUARD" in out
    assert "guard answer" in out

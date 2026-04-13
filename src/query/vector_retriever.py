"""
Vector retriever — searches the store for relevant chunks.

Uses the embedder to convert the query into a vector, then runs
hybrid search (vector kNN + BM25) on the store.

Slice 0.3: basic retrieval. Sprint 1+ adds FlashRank reranking.
"""

from __future__ import annotations

import os
import re

from src.store.lance_store import LanceStore, ChunkResult


class VectorRetriever:
    """Retrieves chunks from the vector store via hybrid search."""

    _QUERY_STOPWORDS = {
        "what",
        "which",
        "when",
        "where",
        "who",
        "why",
        "how",
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "under",
        "program",
        "contract",
        "data",
        "requirements",
        "list",
        "management",
        "plan",
        "priced",
        "bill",
        "materials",
        "integrated",
        "logistics",
        "support",
        "monthly",
        "status",
        "report",
        "reports",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }

    def __init__(
        self,
        store: LanceStore,
        embedder,
        top_k: int = 10,
        candidate_pool: int | None = None,
        nprobes: int | None = None,
        refine_factor: int | None = None,
    ):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.candidate_pool = max(top_k, candidate_pool or top_k)
        self.nprobes = nprobes if nprobes is not None else self._env_int("HYBRIDRAG_LANCE_NPROBES")
        self.refine_factor = (
            refine_factor
            if refine_factor is not None
            else self._env_int("HYBRIDRAG_LANCE_REFINE_FACTOR")
        )
        if self.nprobes is not None or self.refine_factor is not None:
            self.store.configure_search(
                nprobes=self.nprobes,
                refine_factor=self.refine_factor,
            )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        candidate_pool: int | None = None,
    ) -> list[ChunkResult]:
        """
        Search for chunks matching the query.

        Embeds the query, runs hybrid search (vector + BM25).

        ``top_k`` is the caller's target result count. ``candidate_pool``
        controls how many candidates we ask the store for before any
        downstream reranking/trimming. Direct callers that do not want a
        wider pool can omit ``candidate_pool`` and will get exactly
        ``top_k`` back.
        """
        k = top_k or self.top_k
        fetch_k = max(k, candidate_pool or k)
        # Sanitize: strip control chars and limit length to prevent tokenizer errors
        query = "".join(ch for ch in query if ch.isprintable() or ch in ("\n", "\t"))
        query = query[:4096]
        if not query.strip():
            return []
        query_vector = self.embedder.embed_query(query)
        results = self.store.hybrid_search(
            query_vector=query_vector,
            query_text=query,
            top_k=fetch_k,
            nprobes=self.nprobes,
            refine_factor=self.refine_factor,
        )
        path_hits = self._metadata_path_hits(query, fetch_k)
        if not path_hits:
            return results

        merged: list[ChunkResult] = []
        seen: set[str] = set()
        for result in [*path_hits, *results]:
            cid = result.chunk_id or ""
            if cid in seen:
                continue
            seen.add(cid)
            merged.append(result)
        return merged

    def _env_int(self, name: str) -> int | None:
        """Parse an optional positive integer from the environment."""
        raw = os.getenv(name, "").strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value > 0 else None

    def _metadata_path_hits(self, query: str, fetch_k: int) -> list[ChunkResult]:
        """Supplement hybrid retrieval with exact-ish source_path recall."""
        groups = self._path_hint_groups(query)
        if not groups:
            return []

        merged: list[ChunkResult] = []
        seen: set[str] = set()
        for group in groups:
            if not group:
                continue
            hits = self.store.metadata_path_search(group, limit=min(fetch_k, 8))
            for hit in hits:
                cid = hit.chunk_id or ""
                if cid in seen:
                    continue
                seen.add(cid)
                merged.append(hit)
            if len(merged) >= fetch_k:
                break
        return merged[:fetch_k]

    def _path_hint_groups(self, query: str) -> list[list[str]]:
        """Build high-signal metadata path hints from the raw query text."""
        q = " ".join(query.split())
        lower = q.lower()
        groups: list[list[str]] = []

        cdrl = self._extract_cdrl_code(lower)
        deliverable_id = self._extract_deliverable_id(lower)
        cdrl_hints = self._cdrl_title_hints(lower)
        site = self._extract_site_hint(q)
        exact_dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", lower)
        month_terms = re.findall(r"\b20\d{2}[_-]\d{2}\b", lower)

        if deliverable_id:
            for hint in cdrl_hints:
                groups.append([deliverable_id, hint])
            groups.append([deliverable_id])

        if cdrl:
            deliverable_intent = self._has_deliverable_intent(lower)
            if deliverable_intent:
                groups.append([cdrl.lower(), "deliverables report"])
                groups.append([cdrl.lower(), "deliverables"])
                groups.append([cdrl.lower(), "delivered"])
            for hint in cdrl_hints:
                groups.append([cdrl.lower(), hint])
            groups.append([cdrl.lower()])

        if self._looks_like_shipment_query(lower) and site:
            if exact_dates:
                for date in exact_dates[:2]:
                    date_under = date.replace("-", "_")
                    groups.append([site, date_under, "shipments"])
                    groups.append([site, date_under, "packing list"])
                    groups.append([site, date_under])
                    groups.append([site, date, "shipments"])
                    groups.append([site, date])
            if month_terms:
                for month in month_terms[:2]:
                    groups.append([site, month, "shipments"])
                    groups.append([site, month, "packing list"])
                    groups.append([site, month])
            if "return" in lower:
                groups.append([site, "return", "shipments"])
                groups.append([site, "return"])
            groups.append([site, "shipments", "packing list"])
            groups.append([site, "shipments"])
            groups.append([site, "packing list"])

        deduped: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        for group in groups:
            cleaned = tuple(term for term in group if term)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(list(cleaned))
        return deduped

    def _extract_cdrl_code(self, query: str) -> str | None:
        match = re.search(r"\bcdrl(?:\s+is)?\s+(a\d{3})\b", query)
        if match:
            return match.group(1).upper()
        return None

    def _extract_deliverable_id(self, query: str) -> str | None:
        match = re.search(r"\b(igscc-\d+|igsi-\d+)\b", query)
        if match:
            return match.group(1).lower()
        return None

    def _cdrl_title_hints(self, query: str) -> list[str]:
        hints: list[str] = []
        if "maintenance service report" in query:
            hints.extend(["msr", "maintenance service report"])
        if "integrated master schedule" in query:
            hints.extend(["ims", "integrated master schedule"])
        if "configuration change request" in query or "configuration change requests" in query:
            hints.append("configuration change")
        if "corrective action plan" in query:
            hints.extend(["cap", "corrective action plan"])
        if "cybersecurity assessment test report" in query:
            hints.append("cybersecurity assessment test report")
        if "ct&e report" in query or "cte report" in query:
            hints.append("ct&e report")
        if "acas scan" in query or "acas scan results" in query:
            hints.append("acas scan")
        if "scap scan" in query or "scap scan results" in query:
            hints.append("scap scan")
        if "rmf security plan" in query:
            hints.append("rmf security plan")
        if "bill of materials" in query:
            hints.extend(["pbom", "bill of materials"])
        if "management plan" in query:
            hints.extend(["program management plan", "management plan"])
        if "integrated logistics support plan" in query:
            hints.extend(["ilsp", "integrated logistics support plan"])
        if "computer operation manual" in query:
            hints.extend(["com-sum", "computer operation manual"])
        if "software user manual" in query or "software users manual" in query:
            hints.extend(["com-sum", "software user manual"])
        deduped: list[str] = []
        seen: set[str] = set()
        for hint in hints:
            if hint not in seen:
                seen.add(hint)
                deduped.append(hint)
        return deduped

    def _has_deliverable_intent(self, query: str) -> bool:
        return any(
            phrase in query
            for phrase in (
                "what has been delivered",
                "what has been submitted",
                "have been submitted",
                "have been filed",
                "has been filed",
                "archived for",
                "deliverable",
                "deliverables",
            )
        )

    def _looks_like_shipment_query(self, query: str) -> bool:
        return any(token in query for token in ("shipment", "packing list", "shipped to", "return shipment"))

    def _extract_site_hint(self, query: str) -> str | None:
        for token in re.findall(r"\b[A-Z][a-z]{2,}\b", query):
            lowered = token.lower()
            if lowered in self._QUERY_STOPWORDS:
                continue
            return lowered
        return None

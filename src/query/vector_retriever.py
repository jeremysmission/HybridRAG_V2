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
        "show",
        "me",
        "please",
    }

    _KNOWN_SITES = {
        "american samoa",
        "ascension",
        "awase",
        "azores",
        "curacao",
        "diego garcia",
        "djibouti",
        "eglin",
        "fairford",
        "kwajalein",
        "guam",
        "hawaii",
        "learmonth",
        "lualualei",
        "misawa",
        "niger",
        "okinawa",
        "palau",
        "thule",
        "wake",
        "vandenberg",
        "alpena",
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
        typed_hits = self._metadata_field_hits(query, fetch_k)
        path_hits = self._metadata_path_hits(query, fetch_k, typed_hits=typed_hits)
        if not typed_hits and not path_hits:
            return results

        merged: list[ChunkResult] = []
        seen: set[str] = set()
        for result in [*typed_hits, *path_hits, *results]:
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

    def _metadata_field_hits(self, query: str, fetch_k: int) -> list[ChunkResult]:
        """Use typed source metadata when it can replace brittle path guessing."""
        metadata_store = getattr(self.store, "metadata_store", None)
        if metadata_store is None:
            return []

        groups = self._metadata_filter_groups(query)
        if not groups:
            return []

        merged: list[ChunkResult] = []
        seen_sources: set[str] = set()
        per_group_limit = min(max(fetch_k, 8), 16)
        for group in groups:
            source_paths = metadata_store.find_source_paths(limit=per_group_limit, **group)
            if not source_paths:
                continue
            hits = self.store.fetch_source_head_chunks(source_paths, limit=per_group_limit)
            for hit in hits:
                source_path = hit.source_path or ""
                if not source_path or source_path in seen_sources:
                    continue
                seen_sources.add(source_path)
                merged.append(hit)
            if len(merged) >= fetch_k:
                break
        prioritized = self._prioritize_path_hits(query, merged)
        return prioritized[:fetch_k]

    def _metadata_filter_groups(self, query: str) -> list[dict[str, object]]:
        """Build typed metadata filters for the highest-value exact lookup families."""
        q = " ".join(query.split())
        lower = q.lower()

        cdrl_codes = self._extract_cdrl_codes(lower)
        incident_id = self._extract_deliverable_id(lower)
        contract_number = self._extract_contract_number(lower)
        po_number = self._extract_purchase_order_number(lower)
        site = self._extract_known_site(lower) or self._extract_site_hint(q)
        shipment_modes = self._shipment_mode_hints(lower)
        wants_reference_did = self._is_reference_did_query(lower)
        wants_filed = self._has_deliverable_intent(lower) or "filed deliverable" in lower
        source_exts = self._requested_source_exts(lower)

        groups: list[dict[str, object]] = []

        if self._looks_like_cap_query(lower):
            cap_group: dict[str, object] = {
                "cdrl_code": "A001",
                "is_filed_deliverable": True,
            }
            if incident_id:
                cap_group["incident_id"] = incident_id
            if site:
                cap_group["site_terms"] = [site]
            if contract_number:
                cap_group["contract_number"] = contract_number
            if source_exts:
                cap_group["source_exts"] = source_exts
            groups.append(cap_group)
            if incident_id:
                incident_group = {
                    "incident_id": incident_id,
                    "is_filed_deliverable": True,
                }
                if site:
                    incident_group["site_terms"] = [site]
                groups.append(incident_group)

        if po_number:
            po_group: dict[str, object] = {"po_number": po_number}
            if site:
                po_group["site_terms"] = [site]
            if source_exts:
                po_group["source_exts"] = source_exts
            groups.append(po_group)
            groups.append({"po_number": po_number})

        for code in cdrl_codes:
            base: dict[str, object] = {"cdrl_code": code}
            if wants_reference_did:
                base["is_reference_did"] = True
            elif wants_filed:
                base["is_filed_deliverable"] = True
            if contract_number:
                base["contract_number"] = contract_number
            if site:
                base["site_terms"] = [site]
            if source_exts:
                base["source_exts"] = source_exts
            groups.append(base)
            if wants_reference_did:
                groups.append({"cdrl_code": code, "is_reference_did": True})
            if wants_filed:
                groups.append({"cdrl_code": code, "is_filed_deliverable": True})

        if incident_id and not self._looks_like_cap_query(lower):
            incident_group = {"incident_id": incident_id}
            if wants_reference_did:
                incident_group["is_reference_did"] = True
            elif wants_filed or "deliverable" in lower or "submitted" in lower or "filed" in lower:
                incident_group["is_filed_deliverable"] = True
            if site:
                incident_group["site_terms"] = [site]
            if contract_number:
                incident_group["contract_number"] = contract_number
            if source_exts:
                incident_group["source_exts"] = source_exts
            groups.append(incident_group)

        if contract_number and not cdrl_codes and not incident_id and not po_number:
            contract_group: dict[str, object] = {"contract_number": contract_number}
            if wants_filed:
                contract_group["is_filed_deliverable"] = True
            groups.append(contract_group)

        if self._looks_like_shipment_query(lower) and site and (shipment_modes or source_exts):
            shipment_group: dict[str, object] = {"site_terms": [site]}
            if shipment_modes:
                shipment_group["shipment_mode"] = shipment_modes[0]
            if source_exts:
                shipment_group["source_exts"] = source_exts
            groups.append(shipment_group)

        return self._dedupe_filter_groups(groups)

    def _dedupe_filter_groups(self, groups: list[dict[str, object]]) -> list[dict[str, object]]:
        deduped: list[dict[str, object]] = []
        seen: set[tuple[tuple[str, object], ...]] = set()
        for group in groups:
            cleaned = {key: value for key, value in group.items() if value not in ("", [], None)}
            if not cleaned:
                continue
            key = tuple(
                sorted(
                    (
                        item_key,
                        tuple(item_value) if isinstance(item_value, list) else item_value,
                    )
                    for item_key, item_value in cleaned.items()
                )
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped

    def _metadata_path_hits(
        self,
        query: str,
        fetch_k: int,
        typed_hits: list[ChunkResult] | None = None,
    ) -> list[ChunkResult]:
        """Supplement hybrid retrieval with exact-ish source_path recall."""
        groups = self._path_hint_groups(query)
        if not groups:
            return []
        lower_query = query.lower()
        breadth_query = self._requires_path_breadth(lower_query)
        allow_tail_fallback = self._should_allow_path_tail_fallback(
            query,
            typed_hits=typed_hits,
        )
        if not breadth_query:
            groups = sorted(groups, key=self._path_group_priority, reverse=True)

        merged: list[ChunkResult] = []
        seen_sources: set[str] = set()
        per_group_limit = 3 if breadth_query else min(max(fetch_k, 8), 16)
        for group in groups:
            if not group:
                continue
            hits = self.store.metadata_path_search(
                group,
                limit=per_group_limit,
                allow_tail_fallback=allow_tail_fallback,
            )
            for hit in hits:
                source_path = hit.source_path or ""
                if not source_path or source_path in seen_sources:
                    continue
                seen_sources.add(source_path)
                merged.append(hit)
            if len(merged) >= fetch_k:
                break
        prioritized = self._prioritize_path_hits(query, merged)
        return prioritized[:fetch_k]

    def _path_hint_groups(self, query: str) -> list[list[str]]:
        """Build high-signal metadata path hints from the raw query text."""
        q = " ".join(query.split())
        lower = q.lower()
        groups: list[list[str]] = []

        cdrl_codes = self._extract_cdrl_codes(lower)
        deliverable_id = self._extract_deliverable_id(lower)
        site = self._extract_known_site(lower) or self._extract_site_hint(q)
        known_site = self._extract_known_site(lower) or site
        contract_number = self._extract_contract_number(lower)
        po_number = self._extract_purchase_order_number(lower)
        system_hints = self._system_family_hints(lower)
        temporal_hints = self._temporal_path_terms(lower)
        procurement_hints = self._procurement_path_hints(lower)
        exact_dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", lower)
        month_terms = re.findall(r"\b20\d{2}[_-]\d{2}\b", lower)

        if self._looks_like_cap_query(lower) and len(cdrl_codes) <= 1:
            groups.append(["a001", "corrective action plan"])
            groups.append(["corrective action plan", "cap"])
            if deliverable_id:
                groups.append([deliverable_id, "corrective action plan"])
                groups.append([deliverable_id, "a001"])
                if known_site:
                    groups.append([deliverable_id, known_site, "corrective action plan"])
            if known_site:
                groups.append([known_site, "corrective action plan"])
                groups.append([known_site, "a001"])
                for date in exact_dates[:2]:
                    groups.append([known_site, date, "corrective action plan"])

        a027_hints = self._a027_subtype_hints(lower)
        if "a027" in lower and self._looks_like_a027_subtype_aggregate(lower) and not a027_hints:
            a027_hints = self._all_a027_subtype_hints()
        if a027_hints:
            for subtype in a027_hints:
                groups.append(["a027", subtype])
                if contract_number:
                    groups.append(["a027", subtype, contract_number])
                    groups.append([contract_number, subtype])
                if deliverable_id:
                    groups.append([deliverable_id, subtype])
                for system_hint in system_hints:
                    groups.append(["a027", subtype, system_hint])
                for temporal in temporal_hints[:4]:
                    groups.append(["a027", subtype, temporal])
                if known_site:
                    groups.append([known_site, subtype])
            if deliverable_id:
                groups.append([deliverable_id, "a027"])
            if contract_number:
                groups.append(["a027", contract_number])
            groups.append(["a027"])

        if deliverable_id:
            for hint in self._cdrl_title_hints(lower):
                groups.append([deliverable_id, hint])
                for temporal in temporal_hints[:2]:
                    groups.append([deliverable_id, hint, temporal])
            groups.append([deliverable_id])

        if po_number:
            groups.append([po_number])
            if known_site:
                groups.append([po_number, known_site])
            for hint in procurement_hints[:2]:
                groups.append([po_number, hint])

        if self._looks_like_procurement_query(lower):
            vendor_terms = {"pbj", "newark", "dell", "tci", "grainger", "keysight", "dmea", "ldi"}
            for hint in procurement_hints[:3]:
                groups.append([hint])
                if known_site:
                    groups.append([known_site, hint])
            if len(procurement_hints) >= 2:
                groups.append(procurement_hints[:2])
            item_hint = next((hint for hint in procurement_hints if hint not in vendor_terms), None)
            vendor_hint = next((hint for hint in procurement_hints if hint in vendor_terms), None)
            if item_hint and vendor_hint:
                groups.append([item_hint, vendor_hint])
            if known_site and len(procurement_hints) >= 2:
                groups.append([known_site, procurement_hints[0], procurement_hints[1]])

        for code in cdrl_codes:
            code_lower = code.lower()
            code_hints = self._cdrl_code_hints(code, lower)
            if not code_hints:
                code_hints = self._cdrl_title_hints(lower)
            deliverable_intent = self._has_deliverable_intent(lower)
            if deliverable_intent:
                groups.append([code_lower, "deliverables report"])
                groups.append([code_lower, "deliverables"])
                groups.append([code_lower, "delivered"])
            for hint in code_hints:
                groups.append([code_lower, hint])
                if contract_number:
                    groups.append([code_lower, hint, contract_number])
                for system_hint in system_hints:
                    groups.append([code_lower, hint, system_hint])
                for temporal in temporal_hints[:3]:
                    groups.append([code_lower, hint, temporal])
            if contract_number:
                groups.append([code_lower, contract_number])
            groups.append([code_lower])

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
            for temporal in temporal_hints[:4]:
                groups.append([site, temporal, "packing list"])
            if "return" in lower:
                groups.append([site, "return", "shipments"])
                groups.append([site, "return"])
            for mode in self._shipment_mode_hints(lower):
                groups.append([site, mode, "shipments"])
                groups.append([site, mode, "packing list"])
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

    def _extract_cdrl_codes(self, query: str) -> list[str]:
        matches = re.findall(r"\bcdrl(?:\s+is)?\s+(a\d{3})\b", query)
        if not matches and "cdrl" in query:
            matches = re.findall(r"\b(a\d{3})\b", query)
        deduped: list[str] = []
        seen: set[str] = set()
        for match in matches:
            code = match.upper()
            if code in seen:
                continue
            seen.add(code)
            deduped.append(code)
        return deduped

    def _extract_deliverable_id(self, query: str) -> str | None:
        match = re.search(r"\b(igscc-\d+|igsi-\d+)\b", query)
        if match:
            return match.group(1).lower()
        return None

    def _extract_contract_number(self, query: str) -> str | None:
        match = re.search(
            r"\b(fa[a-z0-9]{11}|47qfra[a-z0-9]{7}|[a-z]{2}\d{4}-\d{2}-[a-z]-\d{4})\b",
            query,
        )
        if match:
            return match.group(1).lower()
        return None

    def _extract_purchase_order_number(self, query: str) -> str | None:
        match = re.search(r"\b(?:po[-\s]*)?(5\d{9}|7\d{9})\b", query)
        if match:
            return match.group(1)
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
        if "monthly status report" in query or "monthly status reports" in query:
            hints.append("monthly status report")
        if "configuration audit report" in query:
            hints.append("configuration audit report")
        if "installation acceptance test plan" in query:
            hints.extend(["installation acceptance test plan", "acceptance test plan"])
        if "installation acceptance test report" in query:
            hints.extend(["installation acceptance test report", "acceptance test report"])
        if "bill of materials" in query:
            hints.extend(["pbom", "bill of materials"])
        if "system engineering management plan" in query or "systems engineering management plan" in query:
            hints.extend(["system engineering management plan", "systems engineering management plan", "semp"])
        elif "program management plan" in query:
            hints.extend(["program management plan", "systems mgt plan"])
        elif "management plan" in query:
            hints.append("management plan")
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

    def _cdrl_code_hints(self, code: str, query: str) -> list[str]:
        mapping: dict[str, list[str]] = {
            "A001": ["cap", "corrective action plan"],
            "A002": ["msr", "maintenance service report"],
            "A006": ["installation acceptance test plan", "acceptance test plan"],
            "A007": ["installation acceptance test report", "acceptance test report"],
            "A008": ["program management plan", "management plan", "systems mgt plan"],
            "A009": ["monthly status report"],
            "A011": ["configuration audit report"],
            "A013": ["system engineering management plan", "systems engineering management plan", "semp"],
            "A014": ["pbom", "bill of materials", "priced bill of materials"],
            "A023": ["ilsp", "integrated logistics support plan"],
            "A025": ["com-sum", "computer operation manual", "software user manual"],
        }
        hints = mapping.get(code.upper(), [])
        if code.upper() == "A027":
            hints = self._a027_subtype_hints(query)
            if not hints and self._looks_like_a027_subtype_aggregate(query):
                hints = self._all_a027_subtype_hints()
        return [hint for hint in hints if hint in query or code.upper() in {"A001", "A002", "A006", "A007", "A008", "A009", "A011", "A013", "A014", "A023", "A025", "A027"}]

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

    def _looks_like_cap_query(self, query: str) -> bool:
        if "corrective action plan" in query:
            return True
        if re.search(r"\b(igsi|igscc)-\d+\b", query) and (
            "cap" in query or "corrective" in query or "incident" in query
        ):
            return True
        if re.search(r"\bcap\b", query) and (
            "incident" in query
            or "findings" in query
            or "filed" in query
            or any(site in query for site in self._KNOWN_SITES)
        ):
            return True
        return False

    def _a027_subtype_hints(self, query: str) -> list[str]:
        hints: list[str] = []
        if "acas" in query or "acas scan" in query or "scan results" in query:
            hints.append("acas scan results")
        if "scap" in query:
            hints.append("scap scan")
        if "ct&e" in query or "cte report" in query or "ct and e" in query:
            hints.append("ct&e")
        if "rmf" in query or "rmf security plan" in query:
            hints.append("rmf security plan")
        if "cybersecurity assessment" in query:
            hints.append("cybersecurity assessment test report")
        if "plans and controls" in query or "plan and controls" in query:
            hints.append("plans and controls")
        if "security awareness training" in query:
            hints.extend(["security-awareness", "security-awareness-and-training"])
        if "monthly audit" in query:
            hints.append("monthly audit report")
        if "daa accreditation" in query:
            hints.append("daa accreditation support data")
        deduped: list[str] = []
        seen: set[str] = set()
        for hint in hints:
            if hint not in seen:
                seen.add(hint)
                deduped.append(hint)
        return deduped

    def _all_a027_subtype_hints(self) -> list[str]:
        return [
            "acas scan results",
            "scap scan",
            "ct&e",
            "cybersecurity assessment test report",
            "plans and controls",
            "monthly audit report",
            "rmf security plan",
            "security authorization package",
            "daa accreditation support data",
        ]

    def _looks_like_a027_subtype_aggregate(self, query: str) -> bool:
        return "a027" in query and (
            "subtypes" in query
            or "subtype" in query
            or "deliverable families" in query
            or "how many artifacts are under each" in query
        )

    def _extract_known_site(self, query: str) -> str | None:
        for site in self._KNOWN_SITES:
            if site in query:
                return site
        return None

    def _looks_like_shipment_query(self, query: str) -> bool:
        return any(token in query for token in ("shipment", "packing list", "shipped to", "return shipment"))

    def _extract_site_hint(self, query: str) -> str | None:
        for token in re.findall(r"\b[A-Z][a-z]{2,}\b", query):
            lowered = token.lower()
            if lowered in self._QUERY_STOPWORDS:
                continue
            return lowered
        return None

    def _looks_like_procurement_query(self, query: str) -> bool:
        return any(
            token in query
            for token in (
                "purchase order",
                " received on po ",
                "what was purchase order",
                "what is purchase order",
                "what did we buy",
                "bought from",
                "supplied",
                "supplier",
                "cost",
            )
        ) or bool(self._extract_purchase_order_number(query))

    def _procurement_path_hints(self, query: str) -> list[str]:
        hints: list[str] = []
        phrase_variants = {
            "fieldfox": "field fox",
            "field fox": "field fox",
            "coax crimp kit": "coax crimp",
            "crimp kit": "crimp kit",
            "wire assembly": "wire assembly",
            "pulling tape": "pulling tape",
            "computer cards": "computer cards",
            "rf analyzer": "rf analyzer",
        }
        vendor_terms = ("pbj", "newark", "dell", "tci", "grainger", "keysight", "dmea", "ldi")
        for needle, hint in phrase_variants.items():
            if needle in query:
                hints.append(hint)
        for vendor in vendor_terms:
            if re.search(rf"\b{re.escape(vendor)}\b", query):
                hints.append(vendor)
        deduped: list[str] = []
        seen: set[str] = set()
        for hint in hints:
            if hint in seen:
                continue
            seen.add(hint)
            deduped.append(hint)
        return deduped

    def _system_family_hints(self, query: str) -> list[str]:
        hints: list[str] = []
        if "legacy monitoring system" in query or "isto" in query:
            hints.append("isto")
        if "monitoring system" in query or "nexion" in query:
            hints.append("nexion")
        deduped: list[str] = []
        seen: set[str] = set()
        for hint in hints:
            if hint in seen:
                continue
            seen.add(hint)
            deduped.append(hint)
        return deduped

    def _temporal_path_terms(self, query: str) -> list[str]:
        terms: list[str] = []
        for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", query):
            year, month, day = match.groups()
            terms.extend([f"{year}_{month}_{day}", f"{year}-{month}-{day}", f"{year}_{month}", f"{year}-{month}"])

        month_map = {
            "january": "01",
            "february": "02",
            "march": "03",
            "april": "04",
            "may": "05",
            "june": "06",
            "july": "07",
            "august": "08",
            "september": "09",
            "october": "10",
            "november": "11",
            "december": "12",
        }
        for month_name, month_num in month_map.items():
            for match in re.finditer(rf"\b{month_name}\s+(20\d{{2}})\b", query):
                year = match.group(1)
                terms.extend([
                    f"{month_name}-{year}",
                    f"{month_name} {year}",
                    f"{year}_{month_num}",
                    f"{year}-{month_num}",
                    year,
                ])

        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if term in seen:
                continue
            seen.add(term)
            deduped.append(term)
        return deduped

    def _shipment_mode_hints(self, query: str) -> list[str]:
        hints: list[str] = []
        if "mil-air" in query or "mil air" in query:
            hints.append("mil-air")
        if "hand carry" in query or "hand-carry" in query:
            hints.append("hand carry")
        if "comm" in query:
            hints.append("comm")
        return hints

    def _requested_source_exts(self, query: str) -> list[str]:
        exts: list[str] = []
        if "spreadsheet" in query or "excel" in query or "xlsx" in query:
            exts.extend([".xlsx", ".xls"])
        if "pdf" in query:
            exts.append(".pdf")
        if "docx" in query or "word doc" in query or "word document" in query:
            exts.append(".docx")
        if "ppt" in query or "powerpoint" in query:
            exts.extend([".ppt", ".pptx"])
        deduped: list[str] = []
        seen: set[str] = set()
        for ext in exts:
            if ext in seen:
                continue
            seen.add(ext)
            deduped.append(ext)
        return deduped

    def _is_reference_did_query(self, query: str) -> bool:
        padded = f" {query} "
        return (
            " data item description" in padded
            or " reference did" in padded
            or " reference dids" in padded
            or (
                re.search(r"\bdids?\b", query) is not None
                and any(token in query for token in ("cdrl", "reference", "description"))
            )
        )

    def _path_group_priority(self, group: list[str]) -> tuple[int, int]:
        """Prefer more specific path-term groups before broad family fallbacks."""
        return (len(group), sum(len(term) for term in group))

    def _requires_path_breadth(self, query: str) -> bool:
        """Detect queries that need family breadth instead of one exact file."""
        return (
            self._looks_like_a027_subtype_aggregate(query)
            or len(self._extract_cdrl_codes(query)) > 1
            or query.startswith("which sites appear in both")
            or query.startswith("cross-reference:")
            or query.startswith("cross reference:")
        )

    def _should_allow_path_tail_fallback(
        self,
        query: str,
        typed_hits: list[ChunkResult] | None = None,
    ) -> bool:
        """Keep expensive path fallback for broad queries, not narrow exact lookups."""
        lower_query = query.lower()
        if self._requires_path_breadth(lower_query):
            return True
        if typed_hits:
            return False

        deliverable_id = self._extract_deliverable_id(lower_query)
        contract_number = self._extract_contract_number(lower_query)
        po_number = self._extract_purchase_order_number(lower_query)
        cdrl_codes = self._extract_cdrl_codes(lower_query)
        a027_hints = self._a027_subtype_hints(lower_query)
        temporal_hints = self._temporal_path_terms(lower_query)
        site_hint = self._extract_known_site(lower_query) or self._extract_site_hint(query)

        if po_number:
            return False
        if self._looks_like_procurement_query(lower_query) and (po_number or contract_number):
            return False
        if self._looks_like_shipment_query(lower_query) and site_hint and temporal_hints:
            return False
        if self._looks_like_cap_query(lower_query) and (deliverable_id or site_hint or contract_number):
            return False
        if "a027" in lower_query and a027_hints and (deliverable_id or contract_number or temporal_hints):
            return False
        if len(cdrl_codes) == 1 and (deliverable_id or temporal_hints or self._cdrl_title_hints(lower_query)):
            return False
        return True

    def _prioritize_path_hits(self, query: str, hits: list[ChunkResult]) -> list[ChunkResult]:
        """Prefer live corpus deliverables over reference manuals and archives."""
        if not hits:
            return hits

        lower_query = query.lower()
        logistics_query = self._looks_like_shipment_query(lower_query) or self._looks_like_procurement_query(lower_query)
        po_number = self._extract_purchase_order_number(lower_query)
        contract_number = self._extract_contract_number(lower_query)
        site_hint = self._extract_known_site(lower_query)
        system_hints = self._system_family_hints(lower_query)
        temporal_hints = self._temporal_path_terms(lower_query)
        topical_hints = self._cdrl_title_hints(lower_query) + self._a027_subtype_hints(lower_query)

        def priority(result: ChunkResult) -> tuple[int, int, int, int, int, int, int, int, int]:
            source = result.source_path.lower()
            preferred_corpus = int(
                any(
                    token in source
                    for token in (
                        "\\1.5 igs cdrls\\",
                        "\\1.0 igs dm - restricted\\oasis\\",
                        "\\4.0 configuration_management - restricted\\cm_igs-documents\\contract deliverable documents\\",
                        "\\5.0 logistics\\shipments\\",
                        "\\5.0 logistics\\procurement\\",
                    )
                )
            )
            reference_penalty = int(
                any(
                    token in source
                    for token in (
                        "\\dids\\",
                        "data item description",
                        "documents library",
                        "example program plans",
                        "delete after time",
                        "old versions",
                    )
                )
            )
            archive_penalty = int("\\archive\\" in source)
            exact_po = int(bool(po_number) and po_number in source)
            exact_contract = int(bool(contract_number) and contract_number in source)
            exact_site = int(bool(site_hint) and site_hint in source)
            exact_system = int(any(token in source for token in system_hints))
            exact_time = int(any(token in source for token in temporal_hints[:4]))
            exact_topic = int(any(token in source for token in topical_hints))
            preferred_logistics = int(
                any(token in source for token in ("\\5.0 logistics\\shipments\\", "\\5.0 logistics\\procurement\\"))
            )
            if logistics_query:
                return (
                    preferred_logistics,
                    exact_po,
                    exact_time,
                    exact_site,
                    exact_contract,
                    exact_system,
                    exact_topic,
                    preferred_corpus,
                    -reference_penalty,
                    -archive_penalty,
                )
            return (
                exact_po,
                exact_contract,
                exact_time,
                exact_site,
                exact_system,
                exact_topic,
                preferred_corpus,
                -reference_penalty,
                -archive_penalty,
            )

        return sorted(hits, key=priority, reverse=True)

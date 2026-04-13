# Tier 1 Regex Acceptance Gate - 2026-04-12

Tier 1 is clean enough to rerun only if all four conditions hold:

1. `python -m pytest -q tests/test_extraction.py` passes.
2. Security-standard junk stays out of `PART` and `PO`:
   - SP 800-53 family controls like `IR-4`, `PS-7`, `SA-11`, `SC-51`
   - STIG / DISA identifiers like `AS-5021`, `OS-0004`, `GPOS-0022`, `CCI-0001`, `SV-2045`, `HS-872`
   - MITRE identifiers like `CVE-2024`, `CCE-2720`
3. Purchase-order and part token boundaries stay honest:
   - labeled SAP POs extract only when the label starts on a real token boundary
   - legacy `PO-YYYY-NNNN` extracts as `PO`, never `PART`
   - embedded / partial matches like `repo 5000585586`, `fooPO-2024-1234bar`, `RG-213A`, and `SA-9000X` do not leak
4. Must-preserve positives still survive:
   - labeled SAP POs such as `PO 5000585586`
   - real physical parts such as `ARC-4471`, `RG-213`, `LMR-400`, `PS-800`, `SA-9000`
   - existing phone/date/report-ID positives already pinned in `tests/test_extraction.py`

This gate is for the current enterprise-program corpus. It is a pre-rerun acceptance check, not proof that every downstream aggregate is trustworthy.

Residual risks that still remain after this gate:

- Tier 1 still deliberately does not recover longer alphanumeric part families like `HS-872PEDG2` or `AS-5021202`; those rely on later extraction paths or query-time retrieval.
- The per-corpus `security_standard_exclude_patterns` config remains a wiring risk outside this lane because several extraction entrypoints still instantiate `RegexPreExtractor` from `part_patterns` only. The current corpus is protected by the class default rejection list, but custom override behavior is not what this gate certifies.

# Tier 1 Regex Gate Runbook - 2026-04-12

Run this before any future Tier 1 rerun.

## Purpose

This is a pre-rerun acceptance harness for `RegexPreExtractor`.

It checks:

- curated adversarial cases from existing regex evidence and extractor tests
- curated true-positive cases that must still survive
- an optional read-only live-store sample audit

It does not run Tier 1, does not persist extracted entities, and does not touch the current stores.

## Exact Command

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py
```

Default behavior:

- runs the curated gate
- runs a stratified live-store sample
- selects up to `120` chunks after scanning up to `1,000` chunks

Useful variants:

```powershell
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py --json
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py --sample-limit 300 --max-scan-chunks 5000
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py --sample-mode random --sample-limit 1000
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py --no-sample
```

## Pass / Fail

Pass means:

- every curated false-positive case is rejected
- every curated true-positive case is preserved
- the live sample, if available, emits no security-standard / STIG / MITRE identifiers as `PART` or `PO`
- the live sample, if available, emits no invalid phone garbage as `CONTACT`

Fail means:

- any curated case regresses
- any sampled chunk emits a dangerous `PART` / `PO`
- any sampled chunk emits an invalid phone `CONTACT`

## What The Stratified Sample Means

The default sample mode is `stratified`:

- `security_candidate`: chunk text contains a security-standard/STIG-shaped token
- `phone_candidate`: chunk text contains a phone-like token
- `other`: everything else

This is a read-only audit, not a rerun. It gives a broader preflight signal than the curated cases without writing to the entity store.

## Evidence Basis

The curated gate is derived from:

- `tests/test_extraction.py`
- `docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md`
- `docs/PHONE_REGEX_FIX_2026-04-11.md`

## Residual Blind Spots

- This does not prove the full 10.4M-chunk Tier 1 rerun will be perfect.
- The live sample only audits the current store scan window; it is a gate, not a full-corpus certification.
- This harness covers `RegexPreExtractor` only. It does not certify downstream insert logic or a full persistent rerun.
- If the current LanceDB store is unavailable, the curated gate still runs and the live sample is skipped.

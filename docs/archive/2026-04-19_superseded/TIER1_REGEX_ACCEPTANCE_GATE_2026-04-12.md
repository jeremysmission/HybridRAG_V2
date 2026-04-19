# Tier 1 Regex Acceptance Gate - 2026-04-12

**Scope:** pre-rerun regex / validator hardening for Tier 1 only.

## Short Answer

The Tier 1 regex layer is strong enough to rerun **if and only if** the
current acceptance gate stays green:

- curated adversarial cases pass
- live-store sampling shows no dangerous `PART` / `PO` hits
- live-store sampling shows no invalid phone garbage as `CONTACT`

That gate is already green on the current repo state.

## What Is Actually Enforced Today

The current code already blocks the main collision classes that polluted
Tier 1:

- `PART` pollution from security-standard / STIG / MITRE identifiers
  - security standard SP 800-53 Rev 5 control families
  - STIG baseline codes (`AS-`, `OS-`, `GPOS-`, `HS-`)
  - `CCI-`, `SV-`, `CVE-`, `CCE-`, `SP 800`
- `PO` pollution from the old report-ID overmatch
  - `IR` is no longer part of the report-ID regex
  - only `FSR`, `UMR`, `ASV`, `RTS` remain as report-ID PO candidates
- `PO` pollution from bare 10-digit noise
  - labeled SAP POs are accepted
  - bare 10-digit numbers are intentionally rejected
- phone garbage
  - boundary guards plus validator logic reject embedded / repeated / long-run noise

The key enforcement point is not one giant regex. It is:

1. candidate regex
2. token-boundary checks
3. security-standard exclusion
4. validator rejection

## Evidence On Current Repo State

Validated locally:

- `python -m pytest -q tests\\test_extraction.py tests\\test_tier1_regex_gate.py`
  - `90 passed`
- `python scripts/audit_tier1_regex_gate.py --no-sample`
  - `Curated cases: 40/40 pass`
  - `Verdict: PASS`
- `python scripts/audit_tier1_regex_gate.py --sample-limit 1000`
  - `999 selected / 1000 scanned`
  - `Dangerous PART/PO hits: 0`
  - `Invalid phone hits: 0`
  - `Verdict: PASS`

## Objective Pre-Rerun Gate

Before any Tier 1 rerun, require all of the following:

1. `tests/test_extraction.py` passes.
2. `tests/test_tier1_regex_gate.py` passes.
3. `scripts/audit_tier1_regex_gate.py --no-sample` returns PASS.
4. Optional but recommended: `scripts/audit_tier1_regex_gate.py --sample-limit 1000`
   returns PASS with zero dangerous hits and zero invalid phone hits.

If any of those fail, do not rerun Tier 1.

## Remaining Risks

- The current live sample is a gate, not a full 10.4M-chunk certification.
- The extractor supports corpus-specific exclusion overrides, but the current
  rerun path relies on the default list; if a future corpus needs different
  exclusions, caller wiring must be updated.
- Older narrative docs still contain some historical wording about
  `prefixes`; this acceptance doc is the current operational statement.

## Bottom Line

For the current corpus, the regex / validator layer is good enough to rerun
Tier 1 **after** the gate above is green. That gate is already green on the
current repo state.

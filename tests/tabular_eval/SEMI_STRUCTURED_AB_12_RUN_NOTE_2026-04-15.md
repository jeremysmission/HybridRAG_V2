# Semi-Structured A/B Subset (12 Fixtures)

Pack:
- `tests/tabular_eval/semi_structured_ab_subset_12_2026-04-15.json`

Selection:
- baseline: `table_prompt_mode="baseline"`
- treatment: `table_prompt_mode="synopsis_row_provenance"`

What changes:
- baseline sends the original chunk only
- treatment sends the original chunk plus a compact `[TABLE SYNOPSIS]` block with:
  - `table_mode`
  - `table_family`
  - `header_signatures`
  - `row_provenance`

How to run the first A/B after code lands:
1. Load the 12-fixture pack from `tests/tabular_eval/semi_structured_ab_subset_12_2026-04-15.json`.
2. Run the same extractor/provider over the exact same 12 fixtures twice.
3. First pass: `table_prompt_mode="baseline"`.
4. Second pass: `table_prompt_mode="synopsis_row_provenance"`.
5. Compare the two runs fixture-for-fixture. Do not flip defaults; this lane is opt-in only.

Quick validation:
- `python -m pytest -q tests/test_semi_structured_ab_lane.py`

Notes:
- The pack is fixed to `4 clean labeled + 4 dense semi-structured + 4 OCR-damaged`.
- This lane is intentionally prompt-local. It does not widen the canonical schema or change default extraction behavior.

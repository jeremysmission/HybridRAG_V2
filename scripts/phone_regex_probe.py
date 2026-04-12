"""
Phone Regex Fix Probe - reviewer - 2026-04-11

Reads N chunks from the live 10.4M LanceDB store and runs the Tier 1 regex
extraction with the OLD phone pattern and the NEW phone pattern side by
side. Counts CONTACT entities per pattern, reports before/after, and
extrapolates to the full 10.4M corpus.

READ-ONLY on LanceDB. Does not touch the entity store. Does not touch
tiered_extract.py or import_extract_gui.py.
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

# Torch is loaded by the V2 package even though this script is CPU regex
import torch  # noqa: E402
assert torch.cuda.is_available(), "CUDA required (per instructions)"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

from src.config.schema import load_config  # noqa: E402
from src.store.lance_store import LanceStore  # noqa: E402
from src.extraction.entity_extractor import RegexPreExtractor  # noqa: E402

# The OLD pattern — reproduced inline so we can count its hits without
# reverting the fix. This is the exact pattern from the pre-fix code.
OLD_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")


def old_phone_count(text: str) -> tuple[int, int]:
    """
    Emulate the pre-fix phone extractor on a single chunk.

    Returns (count_all, count_fake) where count_fake is the number of
    old-pattern matches that the new validator would reject.
    """
    matches = list(OLD_PHONE_RE.finditer(text))
    all_count = len(matches)
    fake_count = sum(
        1 for m in matches if not RegexPreExtractor._is_valid_phone(m.group())
    )
    return all_count, fake_count


def main():
    limit = 100_000
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        limit = int(sys.argv[i + 1])

    print("=" * 70)
    print("PHONE REGEX PROBE - reviewer - 2026-04-11")
    print("=" * 70)

    config = load_config(str(v2_root / "config" / "config.yaml"))
    lance_path = str(v2_root / config.paths.lance_db)
    store = LanceStore(lance_path)
    total_chunks = store.count()
    print(f"\nStore: {total_chunks:,} chunks")
    print(f"Sample size: {limit:,} chunks")

    if total_chunks == 0:
        print("ERROR: empty store.")
        sys.exit(1)

    table = store._table

    # Sample N chunks via PyArrow. table.head() and table.search().limit()
    # both return contiguous rows in insertion order — the first 100K turn
    # out to be ~one document, which underestimates phone density to zero.
    # to_arrow() streams the whole table fast (~2s) and lets us pull
    # random offsets for a representative sample across all source docs.
    print("\nLoading chunks via to_arrow()...")
    t0 = time.perf_counter()
    arrow = table.to_arrow()
    arrow_ms = (time.perf_counter() - t0) * 1000
    print(f"Arrow table loaded: {arrow.num_rows:,} rows in {arrow_ms:.0f}ms")

    rng = random.Random(42)
    n_sample = min(limit, arrow.num_rows)
    offsets = sorted(rng.sample(range(arrow.num_rows), n_sample))

    # Extract columns once (Arrow arrays), then slice by index
    text_col = arrow.column("text")
    cid_col = arrow.column("chunk_id")
    src_col = arrow.column("source_path")

    t0 = time.perf_counter()
    chunks = []
    for off in offsets:
        txt = text_col[off].as_py()
        if not txt:
            continue
        chunks.append((
            cid_col[off].as_py(),
            txt,
            src_col[off].as_py() or "",
        ))
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"Sampled {len(chunks):,} chunks (random seed=42) in {load_ms:.0f}ms")

    store.close()

    # Build the new extractor
    extractor = RegexPreExtractor(part_patterns=config.extraction.part_patterns)

    # Metrics
    old_total_phones = 0
    old_fake_phones = 0       # would be rejected by new validator
    old_real_phones = 0       # would be accepted by new validator
    new_phones = 0
    new_emails = 0
    new_parts = 0
    new_dates = 0

    # Bucketed samples for reporting
    sample_fakes: list[str] = []
    sample_reals: list[str] = []
    seen_fake_texts: set[str] = set()
    seen_real_texts: set[str] = set()

    t0 = time.perf_counter()
    for i, (chunk_id, text, source) in enumerate(chunks):
        # Old pattern (emulated)
        all_cnt, fake_cnt = old_phone_count(text)
        old_total_phones += all_cnt
        old_fake_phones += fake_cnt
        old_real_phones += (all_cnt - fake_cnt)

        # Capture a few concrete old-pattern fakes for the report
        if len(sample_fakes) < 20 and fake_cnt > 0:
            for m in OLD_PHONE_RE.finditer(text):
                s = m.group()
                if (not RegexPreExtractor._is_valid_phone(s)
                        and s not in seen_fake_texts):
                    sample_fakes.append(s)
                    seen_fake_texts.add(s)
                    if len(sample_fakes) >= 20:
                        break

        # New extractor (full tier-1 call)
        entities = extractor.extract(text, chunk_id, source)
        for e in entities:
            if e.entity_type == "CONTACT":
                if "@" in e.text:
                    new_emails += 1
                else:
                    new_phones += 1
                    if len(sample_reals) < 20 and e.text not in seen_real_texts:
                        sample_reals.append(e.text)
                        seen_real_texts.add(e.text)
            elif e.entity_type == "PART":
                new_parts += 1
            elif e.entity_type == "DATE":
                new_dates += 1

        if (i + 1) % 10000 == 0:
            print(f"  {i+1:,} chunks processed")

    extract_ms = (time.perf_counter() - t0) * 1000

    print(f"\nExtraction time: {extract_ms:.0f}ms ({extract_ms/len(chunks):.2f}ms/chunk)")

    # --- Compute results ---
    old_contact_total = old_total_phones + new_emails  # old CONTACT = old_phones + emails
    new_contact_total = new_phones + new_emails

    extrap_factor = total_chunks / len(chunks)

    results = {
        "sample_size": len(chunks),
        "corpus_size": total_chunks,
        "extrapolation_factor": round(extrap_factor, 1),
        "old_pattern": {
            "phone_matches_total": old_total_phones,
            "phone_matches_fake": old_fake_phones,
            "phone_matches_real": old_real_phones,
            "contact_total_inc_emails": old_contact_total,
            "fake_rate_pct": round(100 * old_fake_phones / max(old_total_phones, 1), 2),
        },
        "new_pattern": {
            "phone_matches": new_phones,
            "email_matches": new_emails,
            "contact_total": new_contact_total,
            "part_matches": new_parts,
            "date_matches": new_dates,
        },
        "reduction": {
            "contact_absolute": old_contact_total - new_contact_total,
            "contact_pct": round(
                100 * (old_contact_total - new_contact_total) / max(old_contact_total, 1),
                2,
            ),
        },
        "projection_10_4M": {
            "old_contact": int(old_contact_total * extrap_factor),
            "new_contact": int(new_contact_total * extrap_factor),
            "new_phones_only": int(new_phones * extrap_factor),
            "new_emails_only": int(new_emails * extrap_factor),
        },
        "sample_rejected_fakes": sample_fakes,
        "sample_accepted_reals": sample_reals,
    }

    print(f"\n{'='*70}\nRESULTS\n{'='*70}")
    print(f"Old pattern phone matches:        {old_total_phones:,}")
    print(f"  -> fake (rejected by new):      {old_fake_phones:,} ({results['old_pattern']['fake_rate_pct']}%)")
    print(f"  -> real (accepted by new):      {old_real_phones:,}")
    print(f"New pattern phone matches:        {new_phones:,}")
    print(f"New pattern email matches:        {new_emails:,}")
    print(f"Old CONTACT total (phones+emails): {old_contact_total:,}")
    print(f"New CONTACT total (phones+emails): {new_contact_total:,}")
    print(f"Reduction: {results['reduction']['contact_absolute']:,} ({results['reduction']['contact_pct']}%)")
    print(f"\n10.4M corpus projection:")
    print(f"  Old CONTACT (projected):        {results['projection_10_4M']['old_contact']:,}")
    print(f"  New CONTACT (projected):        {results['projection_10_4M']['new_contact']:,}")
    print(f"  New phones only (projected):    {results['projection_10_4M']['new_phones_only']:,}")
    print(f"  New emails only (projected):    {results['projection_10_4M']['new_emails_only']:,}")

    print("\nSample rejected fakes:")
    for s in sample_fakes[:10]:
        print(f"  {s!r}")
    print("\nSample accepted reals:")
    for s in sample_reals[:10]:
        print(f"  {s!r}")

    # Write JSON artifact
    out = v2_root / "docs" / "phone_regex_probe_2026-04-11.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON: {out}")

    print("\nDone.")


if __name__ == "__main__":
    main()

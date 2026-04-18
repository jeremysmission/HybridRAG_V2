"""
Enrich entity store from config/domain_vocab.yaml.
Idempotent — checks before inserting. Safe to re-run.

Usage:
    python scripts/enrich_from_vocab.py [--dry-run]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VOCAB_PATH = REPO_ROOT / "config" / "domain_vocab.yaml"
ENTITY_DB = REPO_ROOT / "data" / "index" / "entities.sqlite3"


def load_vocab():
    with open(VOCAB_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def entity_exists(cur, text, entity_type=None):
    if entity_type:
        cur.execute(
            "SELECT 1 FROM entities WHERE text = ? AND entity_type = ? LIMIT 1",
            (text, entity_type),
        )
    else:
        cur.execute("SELECT 1 FROM entities WHERE text = ? LIMIT 1", (text,))
    return cur.fetchone() is not None


def insert_entity(cur, text, entity_type, confidence=0.9, source_path="domain_vocab.yaml"):
    cur.execute(
        "INSERT INTO entities (text, raw_text, entity_type, confidence, source_path, chunk_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (text, text, entity_type, confidence, source_path, "vocab_enrichment"),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would be inserted without writing")
    args = parser.parse_args()

    if not VOCAB_PATH.exists():
        print(f"ERROR: {VOCAB_PATH} not found")
        sys.exit(1)
    if not ENTITY_DB.exists():
        print(f"ERROR: {ENTITY_DB} not found")
        sys.exit(1)

    vocab = load_vocab()
    conn = sqlite3.connect(str(ENTITY_DB))
    cur = conn.cursor()

    counts = {"acronym": 0, "site": 0, "cdrl_code": 0, "program": 0, "skipped": 0}

    # Acronyms
    acronyms = vocab.get("acronyms", {})
    for acronym, definition in acronyms.items():
        if not entity_exists(cur, acronym, "ACRONYM"):
            if not args.dry_run:
                insert_entity(cur, acronym, "ACRONYM", 0.95)
            counts["acronym"] += 1
        else:
            counts["skipped"] += 1

    # Sites
    sites = vocab.get("sites", [])
    for site in sites:
        if not entity_exists(cur, site, "SITE"):
            if not args.dry_run:
                insert_entity(cur, site, "SITE", 0.99)
            counts["site"] += 1
        else:
            counts["skipped"] += 1

    # CDRL codes
    cdrl_codes = vocab.get("cdrl_codes", {})
    for code, desc in cdrl_codes.items():
        if not entity_exists(cur, code, "CDRL_CODE"):
            if not args.dry_run:
                insert_entity(cur, code, "CDRL_CODE", 0.99)
            counts["cdrl_code"] += 1
        else:
            counts["skipped"] += 1

    # Program names
    programs = vocab.get("program_names", {})
    for name, full in programs.items():
        if not entity_exists(cur, name, "PROGRAM"):
            if not args.dry_run:
                insert_entity(cur, name, "PROGRAM", 0.99)
            counts["program"] += 1
        else:
            counts["skipped"] += 1

    if not args.dry_run:
        conn.commit()
        action = "Inserted"
    else:
        action = "Would insert"

    conn.close()

    total_inserted = counts["acronym"] + counts["site"] + counts["cdrl_code"] + counts["program"]
    print(f"{action}: {counts['acronym']} acronyms, {counts['site']} sites, "
          f"{counts['cdrl_code']} CDRL codes, {counts['program']} programs")
    print(f"Skipped (already present): {counts['skipped']}")
    print(f"Total new: {total_inserted}")


if __name__ == "__main__":
    main()

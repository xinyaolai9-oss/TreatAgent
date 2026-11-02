#!/usr/bin/env python3
"""Create the paper's submission-date-separated (SS) split."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "data/benchmark"
DEFAULT_PAIRS = BENCHMARK / "processed/pair_level_dataset.json"
DEFAULT_DATES = BENCHMARK / "processed/nctid_trial_dates.json"
DEFAULT_OUTPUT_DIR = BENCHMARK / "splits"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def attach_submission_dates(pairs: list[dict], dates: dict) -> list[dict]:
    dated: list[dict] = []
    for row in pairs:
        candidates = []
        for nctid in row.get("nctids", []):
            value = (dates.get(nctid) or {}).get("study_first_submit_date")
            parsed = parse_date(value)
            if parsed:
                candidates.append((parsed, value[:10], nctid))
        if not candidates:
            raise ValueError(f"No study_first_submit_date for {row['pair_id']}")
        candidates.sort(key=lambda item: item[0])
        _, value, nctid = candidates[0]
        enriched = dict(row)
        enriched["pair_date"] = value
        enriched["pair_date_source"] = "study_first_submit_date"
        enriched["pair_date_nctid"] = nctid
        dated.append(enriched)
    return sorted(dated, key=lambda row: (row["pair_date"], row["pair_id"]))


def split_rows(rows: list[dict]) -> dict[str, list[dict]]:
    n_train = round(len(rows) * 0.7)
    n_val = round(len(rows) * 0.1)
    return {
        "train": rows[:n_train],
        "val": rows[n_train:n_train + n_val],
        "test": rows[n_train + n_val:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair_json", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--dates_json", type=Path, default=DEFAULT_DATES)
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    pairs = json.loads(args.pair_json.read_text(encoding="utf-8"))
    dates = json.loads(args.dates_json.read_text(encoding="utf-8"))
    splits = split_rows(attach_submission_dates(pairs, dates))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for partition, values in splits.items():
        path = args.output_dir / f"temporal_submit_{partition}.json"
        text = json.dumps(values, indent=2, ensure_ascii=False).replace("\n", "\r\n")
        path.write_bytes(text.encode("utf-8"))
        print(f"Wrote {len(values)} rows to {path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create the paper's deterministic drug-disjoint (DD) split."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "data/benchmark/processed/pair_level_dataset.json"
DEFAULT_OUTPUT_DIR = ROOT / "data/benchmark/splits"


def split_rows(rows: list[dict], seed: int = 13) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["canonical_smiles"]].append(row)
    group_list = list(groups.values())
    rng.shuffle(group_list)
    group_list.sort(key=len, reverse=True)
    targets = {"train": len(rows) * 0.7, "val": len(rows) * 0.1, "test": len(rows) * 0.2}
    splits = {"train": [], "val": [], "test": []}
    for group in group_list:
        destination = max(splits, key=lambda name: targets[name] - len(splits[name]))
        splits[destination].extend(group)
    for values in splits.values():
        rng.shuffle(values)
    return splits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_json", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    rows = json.loads(args.input_json.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for partition, values in split_rows(rows, args.seed).items():
        path = args.output_dir / f"drug_disjoint_{partition}.json"
        path.write_bytes(json.dumps(values, indent=2, ensure_ascii=False).encode("utf-8"))
        print(f"Wrote {len(values)} rows to {path}")


if __name__ == "__main__":
    main()

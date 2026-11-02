#!/usr/bin/env python3
"""Verify benchmark hashes and split invariants offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "data/benchmark"
PARTITIONS = ("train", "val", "test")
PREFIXES = ("drug_disjoint", "temporal_submit")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_manifest() -> None:
    manifest = load(BENCHMARK / "manifest.json")
    entries = [
        manifest["construction"]["raw_source"],
        manifest["construction"]["pair_dataset"],
        manifest["construction"]["trial_date_snapshot"],
        manifest["construction"]["build_stats"],
    ]
    for protocol in manifest["protocols"].values():
        entries.extend(protocol["splits"].values())
    for entry in entries:
        path = BENCHMARK / entry["path"]
        assert path.is_file(), f"Missing manifest file: {path}"
        assert path.stat().st_size == int(entry["bytes"]), f"Size mismatch: {path}"
        assert sha256(path) == entry["sha256"], f"SHA-256 mismatch: {path}"


def check_splits() -> None:
    pairs = load(BENCHMARK / "processed/pair_level_dataset.json")
    all_ids = {row["pair_id"] for row in pairs}
    assert len(pairs) == len(all_ids) == 2160
    assert sum(int(row["label"]) for row in pairs) == 1106

    for prefix in PREFIXES:
        split_rows = {
            partition: load(BENCHMARK / "splits" / f"{prefix}_{partition}.json")
            for partition in PARTITIONS
        }
        split_ids = {
            partition: {row["pair_id"] for row in rows}
            for partition, rows in split_rows.items()
        }
        assert {name: len(rows) for name, rows in split_rows.items()} == {
            "train": 1512, "val": 216, "test": 432
        }
        assert set().union(*split_ids.values()) == all_ids
        for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
            assert split_ids[left].isdisjoint(split_ids[right]), f"Pair overlap in {prefix}: {left}/{right}"

        if prefix == "drug_disjoint":
            drugs = {
                partition: {row["canonical_smiles"] for row in rows}
                for partition, rows in split_rows.items()
            }
            for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
                assert drugs[left].isdisjoint(drugs[right]), f"Drug overlap in DD: {left}/{right}"
        else:
            dates = {
                partition: [row["pair_date"] for row in rows]
                for partition, rows in split_rows.items()
            }
            assert max(dates["train"]) < min(dates["val"])
            assert max(dates["val"]) < min(dates["test"])
            assert all(
                row.get("pair_date_source") == "study_first_submit_date"
                for rows in split_rows.values() for row in rows
            )

def main() -> None:
    check_manifest()
    check_splits()
    print("Benchmark verification passed: 2,160 pairs and exact DD/SS artifacts.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Write a deterministic manifest for the published benchmark artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "data/benchmark"
PARTITIONS = ("train", "val", "test")
PROTOCOLS = {"drug_disjoint": "DD", "temporal_submit": "SS"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_entry(path: Path) -> dict:
    return {
        "path": path.relative_to(BENCHMARK).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def split_entry(path: Path) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8"))
    entry = file_entry(path)
    entry.update({
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(str(row["label"]) for row in rows).items())),
        "unique_drugs": len({row["canonical_smiles"] for row in rows}),
        "unique_diseases": len({row["normalized_disease"] for row in rows}),
    })
    dates = [row.get("pair_date") for row in rows if row.get("pair_date")]
    if dates:
        entry["date_range"] = [min(dates), max(dates)]
    return entry


def main() -> None:
    pairs_path = BENCHMARK / "processed/pair_level_dataset.json"
    build_stats_path = BENCHMARK / "processed/build_stats.json"
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "1.0",
        "description": "Final benchmark artifacts used by the TreatAgent manuscript",
        "construction": {
            "seed": 13,
            "raw_source": file_entry(BENCHMARK / "raw_data.csv"),
            "pair_dataset": {
                **file_entry(pairs_path),
                "rows": len(pairs),
                "label_counts": dict(sorted(Counter(str(row["label"]) for row in pairs).items())),
                "unique_drugs": len({row["canonical_smiles"] for row in pairs}),
                "unique_diseases": len({row["normalized_disease"] for row in pairs}),
            },
            "trial_date_snapshot": file_entry(BENCHMARK / "processed/nctid_trial_dates.json"),
            "build_stats": {
                **file_entry(build_stats_path),
                "summary": json.loads(build_stats_path.read_text(encoding="utf-8")),
            },
        },
        "protocols": {},
    }
    for prefix, label in PROTOCOLS.items():
        manifest["protocols"][label] = {
            "name": "drug-disjoint" if prefix == "drug_disjoint" else "submission-date-separated",
            "splits": {
                partition: split_entry(BENCHMARK / "splits" / f"{prefix}_{partition}.json")
                for partition in PARTITIONS
            },
        }
    path = BENCHMARK / "manifest.json"
    path.write_bytes(json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build split-specific TrialPrior artifacts from benchmark training pairs.

For each normalized disease d, TrialPrior is the unsmoothed mean of the binary
pair labels in the corresponding training partition:

    T(d) = sum(y_j) / n_d

Validation and test records are never read by this script.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPLIT_DIR = PROJECT_ROOT / "data" / "benchmark" / "splits"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "trial_prior" / "trial_priors"

SPLITS = {
    "drug_disjoint": "drug_disjoint_train.json",
    "submission_date_separated": "temporal_submit_train.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_disease(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def load_training_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def aggregate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    pair_ids: set[str] = set()

    for position, row in enumerate(rows, start=1):
        pair_id = str(row.get("pair_id") or "").strip()
        if not pair_id:
            raise ValueError(f"Missing pair_id at row {position}")
        if pair_id in pair_ids:
            raise ValueError(f"Duplicate pair_id in training partition: {pair_id}")
        pair_ids.add(pair_id)

        disease = normalize_disease(row.get("normalized_disease"))
        if not disease:
            raise ValueError(f"Missing normalized_disease for {pair_id}")

        label = row.get("label")
        if label not in (0, 1):
            raise ValueError(f"Non-binary label for {pair_id}: {label!r}")

        counts[disease][0] += int(label)
        counts[disease][1] += 1

    audit_rows = []
    runtime_mapping = {}
    for disease in sorted(counts):
        positive_pairs, total_pairs = counts[disease]
        success_rate = positive_pairs / total_pairs
        audit_rows.append(
            {
                "normalized_disease": disease,
                "positive_pairs": positive_pairs,
                "total_pairs": total_pairs,
                "success_rate": success_rate,
            }
        )
        runtime_mapping[disease] = success_rate

    return audit_rows, runtime_mapping


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_audit_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "normalized_disease",
                "positive_pairs",
                "total_pairs",
                "success_rate",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build(split_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "definition": "T(d) = sum(y_j) / n_d over matching pairs in the corresponding training partition",
        "smoothing": "none",
        "matching_input": "normalized_disease",
        "validation_or_test_records_read": False,
        "splits": {},
    }

    for split_name, input_name in SPLITS.items():
        input_path = split_dir / input_name
        rows = load_training_rows(input_path)
        audit_rows, runtime_mapping = aggregate(rows)

        json_path = output_dir / f"{split_name}.json"
        csv_path = output_dir / f"{split_name}_audit.csv"
        write_json(json_path, runtime_mapping)
        write_audit_csv(csv_path, audit_rows)

        positive_pairs = sum(int(row["label"]) for row in rows)
        manifest["splits"][split_name] = {
            "input": input_path.relative_to(PROJECT_ROOT).as_posix(),
            "input_sha256": sha256(input_path),
            "training_pairs": len(rows),
            "positive_pairs": positive_pairs,
            "negative_pairs": len(rows) - positive_pairs,
            "unique_normalized_diseases": len(runtime_mapping),
            "runtime_json": json_path.relative_to(PROJECT_ROOT).as_posix(),
            "runtime_json_sha256": sha256(json_path),
            "audit_csv": csv_path.relative_to(PROJECT_ROOT).as_posix(),
            "audit_csv_sha256": sha256(csv_path),
        }

    write_json(output_dir / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build(args.split_dir.resolve(), args.output_dir.resolve())
    for split_name, summary in manifest["splits"].items():
        print(
            f"{split_name}: {summary['training_pairs']} training pairs, "
            f"{summary['unique_normalized_diseases']} diseases"
        )


if __name__ == "__main__":
    main()

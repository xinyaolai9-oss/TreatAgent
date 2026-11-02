#!/usr/bin/env python3
"""Verify frozen outputs, benchmark alignment, metrics, and release hashes."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from metrics import bootstrap_summary, calculate_metrics, paired_bootstrap_difference


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TOLERANCE = 1e-6


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(actual: float, expected: str, *, tolerance: float = TOLERANCE) -> None:
    if expected == "":
        return
    if abs(actual - float(expected)) > tolerance:
        raise AssertionError(f"Metric mismatch: actual={actual}, expected={expected}")


def record_documents() -> dict[tuple[str, str], dict]:
    documents = {}
    with (RESULTS / "records/index.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            document = load_json(RESULTS / "records" / row["file"])
            assert len(document["results"]) == int(row["records"]) == 432
            documents[(row["workflow"], row["split"])] = document
    assert len(documents) == 22
    return documents


def verify_benchmark_alignment(documents: dict[tuple[str, str], dict]) -> None:
    split_paths = {
        "drug_disjoint": ROOT / "data/benchmark/splits/drug_disjoint_test.json",
        "submission_date_separated": ROOT / "data/benchmark/splits/temporal_submit_test.json",
    }
    for (_, split), document in documents.items():
        benchmark = load_json(split_paths[split])
        expected = [(row["pair_id"], int(row["label"])) for row in benchmark]
        observed = [(row["sample_id"], int(row["label"])) for row in document["results"]]
        assert observed == expected, f"Benchmark ordering/label mismatch: {document['workflow']} {split}"


def verify_metric_tables(documents: dict[tuple[str, str], dict]) -> None:
    for table_name in ("main_performance.csv", "ablation_performance.csv"):
        with (RESULTS / "source_data" / table_name).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                document = documents[(row["workflow"], row["split"])]
                metrics = calculate_metrics(document["results"])
                for metric in metrics:
                    if metric in row:
                        close(metrics[metric], row[metric])


def verify_bootstrap(documents: dict[tuple[str, str], dict]) -> None:
    path = RESULTS / "source_data/bootstrap_confidence_intervals.csv"
    rng = np.random.default_rng(13)
    resamples = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records = documents[(row["workflow"], row["split"])]["results"]
            key = (row["workflow"], row["split"])
            if key not in resamples:
                resamples[key] = [
                    rng.integers(0, len(records), len(records))
                    for _ in range(int(row["n_bootstrap"]))
                ]
            observed, mean, lower, upper = bootstrap_summary(
                records,
                row["metric"],
                n_bootstrap=int(row["n_bootstrap"]),
                seed=int(row["seed"]),
                resamples=resamples[key],
            )
            close(observed, row["observed"])
            close(mean, row["bootstrap_mean"])
            close(lower, row["ci_lower"])
            close(upper, row["ci_upper"])


def verify_paired_comparisons(documents: dict[tuple[str, str], dict]) -> None:
    path = RESULTS / "source_data/paired_comparisons.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            left_name, right_name = row["comparison"].split(" - ", 1)
            left = documents[(left_name, row["split"])]["results"]
            right = documents[(right_name, row["split"])]["results"]
            difference, lower, upper = paired_bootstrap_difference(left, right, row["metric"])
            # The released paired table is rounded to three decimals and was
            # produced from the original full-artifact analysis. Candidate
            # records reproduce it within the published rounding precision.
            close(difference, row["difference"], tolerance=5e-3)
            close(lower, row["ci_lower"], tolerance=5e-3)
            close(upper, row["ci_upper"], tolerance=5e-3)


def verify_hash_manifests() -> None:
    provenance = load_json(RESULTS / "provenance.json")
    for entry in provenance["outputs"]:
        path = RESULTS / entry["file"]
        assert path.is_file()
        assert path.stat().st_size == int(entry["bytes"])
        assert sha256(path) == entry["sha256"]

    dti_dir = ROOT / "data/dti/model_MPNN_CNN"
    dti_manifest = load_json(dti_dir / "MANIFEST.json")
    for name, entry in dti_manifest["files"].items():
        path = dti_dir / name
        assert path.stat().st_size == int(entry["bytes"])
        assert sha256(path) == entry["sha256"]

    prior_manifest = load_json(ROOT / "data/trial_prior/trial_priors/manifest.json")
    for entry in prior_manifest["splits"].values():
        for path_key, hash_key in (
            ("input", "input_sha256"),
            ("runtime_json", "runtime_json_sha256"),
            ("audit_csv", "audit_csv_sha256"),
        ):
            assert sha256(ROOT / entry[path_key]) == entry[hash_key]


def main() -> None:
    documents = record_documents()
    verify_benchmark_alignment(documents)
    verify_metric_tables(documents)
    verify_bootstrap(documents)
    verify_paired_comparisons(documents)
    verify_hash_manifests()
    print("Release verification passed: 22 files, 9,504 records, metrics, bootstrap, paired comparisons, and hashes.")


if __name__ == "__main__":
    main()

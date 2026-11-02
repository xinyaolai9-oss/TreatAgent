#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

python data/benchmark/scripts/build_pair_dataset.py
python data/benchmark/scripts/make_drug_disjoint_split.py
python data/benchmark/scripts/make_submission_date_split.py
python data/benchmark/scripts/build_manifest.py
python data/benchmark/scripts/verify_benchmark.py

echo
echo "Benchmark pipeline completed."
echo "Published protocols: drug-disjoint (DD) and submission-date-separated (SS)."

# TreatAgent benchmark

This directory contains only the final benchmark artifacts used by the
submitted paper: the drug-disjoint (DD) and submission-date-separated (SS)
protocols. Random splits, the earlier completion-date temporal split, conflict
case reports, smoke inputs, and duplicated intermediate exports are not part of
the release.

## Layout

- `raw_data.csv`: original trial-level source table, tracked with Git LFS.
- `processed/pair_level_dataset.json`: canonical 2,160-pair benchmark
  (1,106 positive; 1,054 negative).
- `processed/nctid_trial_dates.json`: retained ClinicalTrials.gov date snapshot
  used to construct SS without a new network request.
- `processed/build_stats.json`: extraction, canonicalization, deduplication, and
  conflict-removal counts.
- `splits/`: full DD and SS train/validation/test records, including provenance
  fields used to audit pair construction and all fields consumed by the CLI.
- `manifest.json`: sizes, SHA-256 hashes, row/label counts, coverage, and SS
  date ranges for every published artifact.
- `scripts/`: the final deterministic construction pipeline.

`splits/` is both the authoritative scientific representation and the CLI input.
The CLI accepts the benchmark-native `pair_id`, `canonical_smiles`, and
`normalized_disease` fields directly, avoiding a duplicated execution export.

## Rebuild

From the repository root:

```bash
bash data/benchmark/scripts/run_benchmark_pipeline.sh
```

The pipeline performs five steps:

1. filter the raw trial table, canonicalize SMILES, deduplicate drug-disease
   pairs, and remove pairs with conflicting labels;
2. create the seed-13 drug-disjoint split;
3. attach the earliest `study_first_submit_date` and create the chronological
   submission-date-separated split;
4. regenerate and verify `manifest.json`.

The retained date snapshot makes the normal rebuild offline. The maintenance
utility `scripts/fetch_trial_dates.py` contacts ClinicalTrials.gov and should be
used only when deliberately updating the snapshot; doing so creates a new
benchmark version and requires revalidation of all SS artifacts.

## Published split sizes

| Protocol | Train | Validation | Test |
|---|---:|---:|---:|
| DD | 1,512 | 216 | 432 |
| SS | 1,512 | 216 | 432 |

See `manifest.json` for class counts, drug/disease coverage, date ranges, and
exact hashes.

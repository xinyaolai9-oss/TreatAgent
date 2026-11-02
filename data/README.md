# Data Layout

This directory stores the benchmark, runtime expert data, knowledge snapshots,
priors, and dataset-specific preparation scripts included with the standalone
TreatAgent release package.

This package is intended to be runnable after cloning when Git LFS files have
been fetched. It includes processed/runtime expert artifacts rather than large
third-party raw dumps.

## Current Structure

- `benchmark/`
  - Final paper benchmark; see `benchmark/README.md` and `manifest.json`.
  - `raw_data.csv`: original tabular source.
  - `scripts/`: deterministic DD/SS construction and audit pipeline.
  - `processed/`: canonical pair dataset, build counts, and retained trial-date snapshot.
  - `splits/`: authoritative, CLI-ready DD/SS train/validation/test records.

- `trial_prior/`
  - Split-specific disease-level historical outcome statistics used by the
    TrialPrior tool.
  - `build_trial_priors.py`: deterministically rebuilds both priors using only
    the corresponding training partition.
  - `trial_priors/drug_disjoint.json` and
    `trial_priors/submission_date_separated.json`: runtime mappings for the
    reported DD and SS evaluations, with count-level audit CSVs and hashes.
  - Runtime selection is split-safe: the CLI infers DD/SS from the input
    filename or requires an explicit split/path for custom inputs.

- `drugcentral/`
  - DrugInfo assets derived from DrugCentral.
  - The paper used DrugCentral version 54, snapshot dated 1 November 2023;
    generated records retain the snapshot tag `11012023`.
  - Includes generated `druginfo.jsonl`, coverage audit files, and DrugInfo builder
    scripts.
  - The raw DrugCentral SQL dump is not included because it is a multi-GB
    third-party source file and cannot be pushed to a normal GitHub repository.

- `diseaseinfo/`
  - DiseaseInfo assets derived from MONDO and Open Targets.
  - The paper used Mondo release 2026-04-07 and Open Targets release 26.03;
    generated records retain the Open Targets release tag `26.03`.
  - Includes generated `diseaseinfo.jsonl` and DiseaseInfo builder scripts.
  - Raw MONDO/Open Targets snapshots are not included; rebuild them from the
    original sources if needed.

- `dti/`
  - UniProt sequence cache used by the DTI expert.
  - `model_MPNN_CNN/`: exact DeepPurpose `MPNN_CNN_BindingDB` checkpoint used
    by the paper, plus a SHA-256 manifest. Binary files are tracked with LFS.

## GitHub Large File Note

`data/diseaseinfo/diseaseinfo.jsonl` is larger than GitHub's normal per-file limit
for regular Git pushes. This release package includes `.gitattributes` so it can
be tracked with Git LFS.

## Licensing

Original TreatAgent preparation scripts are covered by the repository's
Apache License 2.0. Data, database-derived records, trial-derived benchmark
artifacts, protein sequences, and model checkpoints are not relicensed under
Apache-2.0 or the project CC BY 4.0 grant. Their upstream terms continue to
apply; see [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Recommended Convention

- Keep reusable raw or curated datasets under `data/`.
- Keep dataset-specific Python preparation scripts under that dataset's `scripts/` subdirectory.
- Keep final dataset construction and verification utilities beside their data.
- Keep lightweight TrialPrior artifacts under `data/trial_prior/`.
- Keep large domain knowledge snapshots under dedicated folders such as `data/drugcentral/` and `data/diseaseinfo/`.

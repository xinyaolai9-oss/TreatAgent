# Frozen manuscript results

This directory contains the paper-aligned release view generated from the final
frozen artifacts under `TreatAgent-data/results`.

- `records/`: **primary human-readable entry point**. It contains one formatted
  JSON document per workflow and split, plus an `index.csv` with source hashes,
  thresholds, and row counts. Start with `records/README.md`.
- `source_data/`: only the four aggregate tables required by the final main
  text, Figure 3, and Supplementary Tables S5--S7.
- `case_studies/`: the three representative assessments reported in the paper,
  using the same run/result JSON schema as `records/` and current CLI output.
- `expert_review/`: privacy-safe aggregate results for the exploratory
  14-submission, 16-case evaluation. Respondent-level records are not included;
  see its README for the source-export identity caveat.
- `provenance.json`: audit-only source/output hashes, row counts, and file
  inventory. It contains no model predictions and is not required to interpret
  an individual result; it exists so the frozen release can be verified.

RAG+Tools uses its latest continuous `prediction_score` and the DD-validation-
selected threshold of 0.40. TreatAgent uses `llm_judge_probability` and the
frozen threshold of 0.20.

The approximately 1.4 GB baseline/ablation JSON inputs are not copied verbatim:
they contain extensive repeated runtime state. The release instead retains all
9,504 candidate decisions in the same schema written by the current CLI. Both
paths use `treatagent/result_schema.py`, while source SHA-256 hashes link every
formatted file to its frozen input. One-time conversion and audit utilities
used during repository preparation were removed from the final release.

## License

Original TreatAgent result artifacts and documentation in this directory are
licensed under CC BY 4.0, subject to the exclusions and upstream rights
described in [`LICENSES/README.md`](../LICENSES/README.md) and
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

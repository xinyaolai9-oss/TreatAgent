# Paper-aligned candidate records

This is the primary human-readable entry point for the frozen candidate-level
outputs. `index.csv` lists every workflow, split, threshold, source file, and
source SHA-256 hash.

- `baselines/` contains Direct, CoT, RAG+Tools, and the complete TreatAgent
  workflow from the frozen baseline directory.
- `ablations/` contains the seven component ablations for both DD and SS.

Each JSON document has the exact schema produced by the current CLI. The
release builder and `treatagent.cli` both call `treatagent.result_schema`; these
files are frozen conversions rather than a separate presentation format. Each
document contains the run-level `metrics`, method, threshold, split, metadata,
provenance, and a `results` array with 432 candidates in benchmark order.

Each result keeps the executable output fields (`sample_id`, candidate inputs,
label, method, score, binary decision, and threshold) plus two readable nested
fields: `model_output` for the method-specific answer and `evidence_summary`
for queried sources, representative claims, coverage, and planner trace.

TreatAgent and its ablations expose only the streamlined final-review fields:
`treatment_score`, `confidence`, `uncertainty`, `grade_reason`, `key_support`,
`key_conflict`, `missing_evidence`, and `reasoning_summary`. Legacy frozen
module labels are normalized to `DrugInfo`, `DiseaseInfo`, and `TrialPrior`
during release construction; the archived source file and hash remain in each
document header.

Direct and CoT raw free-text responses were not retained in the frozen files,
so these records state that limitation explicitly instead of reconstructing
reasoning that is no longer available.

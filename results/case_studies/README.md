# Paper case studies

These three frozen assessments use the same JSON schema and shared
serializer as current CLI runs and the baseline/ablation records.
Each file contains one result; run-level metrics are empty because the
cases are qualitative illustrations rather than a separate benchmark.

| Case | ID | Score | Decision | File |
|---|---|---:|---:|---|
| Mavacamten–symptomatic obstructive hypertrophic cardiomyopathy | RECENT-009 | 0.75 | 1 | `mavacamten_ohcm.json` |
| Pirtobrutinib–chronic lymphocytic leukemia | RECENT-008 | 0.63 | 1 | `pirtobrutinib_cll.json` |
| Palbociclib–melanoma | RECENT-011 | 0.19 | 0 | `palbociclib_melanoma.json` |

The `provenance` object in each file records the frozen source artifact
and SHA-256 hash. Legacy source labels were normalized only during this
archival conversion to DrugInfo, DiseaseInfo, and TrialPrior.

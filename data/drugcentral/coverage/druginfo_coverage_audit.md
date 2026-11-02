# DrugInfo Coverage Audit

This audit reports how benchmark drug inputs map to the local DrugCentral-derived DrugInfo.

| split | rows | matched | matched rate | unique SMILES | unique matched DrugCentral records | top match methods |
|---|---:|---:|---:|---:|---:|---|
| drug_disjoint_train.json | 1512 | 1237 | 0.818 | 362 | 263 | ambiguous_connectivity_relaxed: 1, canonical_smiles: 1079, connectivity_relaxed: 55, inchikey: 90, parent_connectivity_relaxed: 12, unmatched: 275 |
| drug_disjoint_val.json | 216 | 140 | 0.648 | 193 | 119 | ambiguous_connectivity_relaxed: 1, canonical_smiles: 121, connectivity_relaxed: 7, inchikey: 10, parent_connectivity_relaxed: 1, unmatched: 76 |
| drug_disjoint_test.json | 432 | 334 | 0.773 | 273 | 198 | canonical_smiles: 300, connectivity_relaxed: 6, inchikey: 27, parent_connectivity_relaxed: 1, unmatched: 98 |
| temporal_submit_train.json | 1512 | 1177 | 0.778 | 665 | 461 | canonical_smiles: 1017, connectivity_relaxed: 58, inchikey: 89, parent_connectivity_relaxed: 13, unmatched: 335 |
| temporal_submit_val.json | 216 | 177 | 0.819 | 140 | 109 | canonical_smiles: 162, connectivity_relaxed: 3, inchikey: 12, unmatched: 39 |
| temporal_submit_test.json | 432 | 357 | 0.826 | 242 | 194 | ambiguous_connectivity_relaxed: 2, canonical_smiles: 321, connectivity_relaxed: 7, inchikey: 26, parent_connectivity_relaxed: 1, unmatched: 75 |

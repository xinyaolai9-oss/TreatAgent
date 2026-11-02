# Final manuscript source data

Only tables required to support the final submitted manuscript are retained:

- `main_performance.csv`: main and Supplementary Table S5 metrics and Figure 3a–c.
- `bootstrap_confidence_intervals.csv`: 1,000-resample percentile intervals
  (seed 13), including the F1 intervals reported in the manuscript.
- `ablation_performance.csv`: Supplementary Table S6 and Figure 3d–e.
- `paired_comparisons.csv`: rounded differences and intervals reported in
  Supplementary Table S7.

Unrounded candidate-level labels, scores, and decisions remain under
`../records/` and are the primary computational source. Early diagnostic
subsets, duplicate summaries, Markdown renderings, and source tables for a
superseded figure were intentionally removed from the final release.

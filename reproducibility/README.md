# Reproducing the frozen release

These lightweight scripts operate on the candidate-level JSON under
`results/records/`; they do not rerun GPT-4 or overwrite frozen results.

Run the complete offline audit from the repository root:

```bash
python reproducibility/verify_release.py
```

The verifier checks all 22 result files and 9,504 candidate records against the
DD/SS benchmark ordering and labels, recalculates the manuscript metrics,
repeats the seed-13 1,000-resample percentile bootstrap and paired comparisons,
and verifies result, TrialPrior and DTI checkpoint hashes.

Render data-level versions of Figures 2--4:

```bash
python reproducibility/render_release_figures.py --output-dir reproduced_figures
```

The generated PDFs reproduce the underlying benchmark, performance and case
study values. They intentionally do not attempt to duplicate the submitted
figures' final typography or manual panel composition.

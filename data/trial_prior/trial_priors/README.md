# Split-specific TrialPrior artifacts

These files contain the disease-level historical outcome statistic used by the
TrialPrior tool. For each normalized disease `d` in a training partition:

```text
T(d) = number of positive training pairs for d / number of training pairs for d
```

No smoothing is applied. Validation and test labels are not read. The runtime
JSON files map normalized disease names to `T(d)`; the corresponding audit CSV
files retain the positive and total pair counts behind every value.

- `drug_disjoint.json`: prior derived from `drug_disjoint_train.json`.
- `submission_date_separated.json`: prior derived from
  `temporal_submit_train.json`.
- `manifest.json`: input/output hashes, counts, and construction definition.

Regenerate all artifacts from the repository root with:

```bash
python data/trial_prior/build_trial_priors.py
```

At runtime, select the corresponding prior before starting TreatAgent:

```bash
TREATAGENT_TRIAL_PRIOR_SPLIT=drug_disjoint python -m treatagent.cli ...
TREATAGENT_TRIAL_PRIOR_SPLIT=submission_date_separated python -m treatagent.cli ...
```

On PowerShell, set the same variable through `$env:TREATAGENT_TRIAL_PRIOR_SPLIT`.
The legacy `data/trial_prior/disease_success_ratio.json` remains available only for
backward compatibility and must not be used for the reported DD/SS evaluation.

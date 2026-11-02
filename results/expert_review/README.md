# Exploratory expert review

This directory contains the privacy-safe aggregate results supporting the
exploratory expert evaluation in Supplementary Table S11. Fourteen submitted
questionnaires each covered the same 16 held-out cases, yielding 224 case-level
judgments.

## Files

- `aggregate_expert_review_results.csv`: aggregate case-level preferences,
  confidence and information-sufficiency outcomes, plus the overall usability
  counts reported in the paper.
- `aggregate_reviewer_characteristics.csv`: unlinked counts for professional
  role, expertise, experience and familiarity.
- `case_manifest.csv`: the 16 reviewed candidates and their benchmark context.
  Benchmark labels, predictions and confusion types were hidden from reviewers.

## Review protocol

Summary A was the natural-paragraph/free-text retrieval summary and Summary B
was the structured candidate/source summary for every case. Summary order and
case order were fixed rather than randomized or counterbalanced. Reviewers were
not shown method names, benchmark labels, trial identifiers, trial outcomes or
whether a prediction was correct.

The 16 cases comprise nine drug-disjoint and seven submission-date-separated
examples: six true positives, six true negatives, two false positives and two
false negatives. The main descriptive findings are:

- structured summary preferred as more useful: 129/224 (57.6%);
- structured summary preferred as more source-traceable: 162/224 (72.3%);
- structured summary preferred for selecting the next step: 149/224 (66.5%);
- mean confidence: 2.97 before summary review and 3.61 after both summaries;
- insufficient-information judgments: 17/224 before and 8/224 after review.

These are descriptive usability outcomes. Because every reviewer saw Summary A
before Summary B, changes after review cannot be attributed specifically to the
structured format. The evaluation did not assess clinical correctness or
prospective utility.

## Privacy and data-quality boundary

The public release excludes the raw questionnaire workbook, IP addresses,
submission metadata, respondent-entered identifiers, respondent-linked
background variables, free-text answers and pseudonymized respondent-level
records. With a cohort of this size, response patterns and free text could
retain re-identification risk even after direct identifiers were removed.

The source export contains 14 completed submissions but 13 distinct
respondent-entered identifiers because one identifier occurred twice. The
source therefore establishes 14 submissions; the number of unique individuals
cannot be independently confirmed from the export alone. This caveat does not
change the 224 submitted case-level judgments used in the aggregate analysis.

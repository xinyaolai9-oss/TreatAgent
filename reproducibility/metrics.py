"""Metric and resampling utilities used by the frozen-result audit."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)


def arrays(records: Sequence[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = np.asarray([int(row["label"]) for row in records], dtype=int)
    decisions = np.asarray([int(row["prediction_binary"]) for row in records], dtype=int)
    scores = np.asarray([float(row["prediction_score"]) for row in records], dtype=float)
    return labels, decisions, scores


def calculate_metrics(records: Sequence[dict[str, Any]]) -> dict[str, float]:
    labels, decisions, scores = arrays(records)
    true_negative = int(((labels == 0) & (decisions == 0)).sum())
    negatives = int((labels == 0).sum())
    queried = [
        len((row.get("evidence_summary") or {}).get("queried_sources") or [])
        for row in records
        if row.get("evidence_summary") is not None
    ]
    return {
        "accuracy": accuracy_score(labels, decisions),
        "f1": f1_score(labels, decisions, zero_division=0),
        "precision": precision_score(labels, decisions, zero_division=0),
        "recall": recall_score(labels, decisions, zero_division=0),
        "specificity": true_negative / negatives if negatives else 0.0,
        "balanced_accuracy": balanced_accuracy_score(labels, decisions),
        "mcc": matthews_corrcoef(labels, decisions),
        "positive_call_rate": float(decisions.mean()),
        "auroc": roc_auc_score(labels, scores),
        "auprc": average_precision_score(labels, scores),
        "mean_tool_calls": float(np.mean(queried)) if queried else float("nan"),
    }


def metric_function(name: str) -> Callable[[np.ndarray, np.ndarray, np.ndarray], float]:
    functions = {
        "accuracy": lambda y, p, s: accuracy_score(y, p),
        "f1": lambda y, p, s: f1_score(y, p, zero_division=0),
        "precision": lambda y, p, s: precision_score(y, p, zero_division=0),
        "recall": lambda y, p, s: recall_score(y, p, zero_division=0),
        "balanced_accuracy": lambda y, p, s: balanced_accuracy_score(y, p),
        "auroc": lambda y, p, s: roc_auc_score(y, s),
        "auprc": lambda y, p, s: average_precision_score(y, s),
        "missed_positive_rate": lambda y, p, s: 1.0 - recall_score(y, p, zero_division=0),
    }
    try:
        return functions[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported metric: {name}") from exc


def bootstrap_summary(
    records: Sequence[dict[str, Any]],
    metric: str,
    *,
    n_bootstrap: int = 1000,
    seed: int = 13,
    resamples: Sequence[np.ndarray] | None = None,
) -> tuple[float, float, float, float]:
    labels, decisions, scores = arrays(records)
    function = metric_function(metric)
    observed = function(labels, decisions, scores)
    if resamples is None:
        rng = np.random.default_rng(seed)
        resamples = [rng.integers(0, len(labels), len(labels)) for _ in range(n_bootstrap)]
    values = []
    for indices in resamples:
        sampled_labels = labels[indices]
        if metric in {"auroc", "auprc"} and len(np.unique(sampled_labels)) < 2:
            continue
        values.append(function(sampled_labels, decisions[indices], scores[indices]))
    lower, upper = np.percentile(values, [2.5, 97.5])
    return float(observed), float(np.mean(values)), float(lower), float(upper)


def paired_bootstrap_difference(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
    metric: str,
    *,
    n_bootstrap: int = 1000,
    seed: int = 13,
) -> tuple[float, float, float]:
    left_labels, left_decisions, left_scores = arrays(left)
    right_labels, right_decisions, right_scores = arrays(right)
    if not np.array_equal(left_labels, right_labels):
        raise ValueError("Paired records do not have identical labels and ordering.")
    function = metric_function(metric)
    observed = function(left_labels, left_decisions, left_scores) - function(
        right_labels, right_decisions, right_scores
    )
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(n_bootstrap):
        indices = rng.integers(0, len(left_labels), len(left_labels))
        sampled_labels = left_labels[indices]
        if metric in {"auroc", "auprc"} and len(np.unique(sampled_labels)) < 2:
            continue
        differences.append(
            function(sampled_labels, left_decisions[indices], left_scores[indices])
            - function(sampled_labels, right_decisions[indices], right_scores[indices])
        )
    lower, upper = np.percentile(differences, [2.5, 97.5])
    return float(observed), float(lower), float(upper)

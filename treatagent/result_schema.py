"""Canonical JSON schema builders for TreatAgent evaluation outputs.

Both live CLI runs and conversions of frozen manuscript artifacts use these
builders. Keeping construction in one module prevents the release records from
quietly drifting away from what the executable code writes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence


RESULT_SCHEMA_VERSION = "1.0"

WORKFLOW_BY_METHOD = {
    "direct": "Direct",
    "cot": "CoT",
    "rag": "RAG+Tools",
    "multiagent": "TreatAgent",
}

WORKFLOW_DESCRIPTIONS = {
    "Direct": "Minimal-input direct prompting with a parsed binary answer.",
    "CoT": "Minimal-input chain-of-thought prompting with a parsed binary answer.",
    "RAG+Tools": "Non-adaptive retrieval from all five sources followed by a continuous RAG review score.",
    "TreatAgent": "Planner-selected evidence acquisition, candidate-level integration, and final evidence review.",
}


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workflow_for_method(method: str) -> str:
    try:
        return WORKFLOW_BY_METHOD[method]
    except KeyError as exc:
        raise ValueError(f"Unsupported result method: {method}") from exc


def score_semantics(method: str) -> str:
    if method in {"direct", "cot"}:
        return "binary_output"
    return "continuous_research_priority"


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def build_model_output(
    *,
    method: str,
    prediction_score: float,
    prediction_binary: int,
    analysis: Mapping[str, Any] | None = None,
    rag_score_analysis: str | None = None,
    rag_uncertainty: str | None = None,
    raw_response: str | None = None,
    retention_note: str | None = None,
) -> dict[str, Any]:
    """Build the method-specific portion of one canonical result record."""
    if method == "direct":
        output = {
            "answer": int(prediction_binary),
            "raw_response": raw_response,
        }
    elif method == "cot":
        output = {
            "analysis": None,
            "answer": int(prediction_binary),
            "raw_response": raw_response,
        }
    elif method == "rag":
        output = {
            "analysis": rag_score_analysis or "",
            "research_priority_score": float(prediction_score),
            "uncertainty": rag_uncertainty or None,
            "raw_response": raw_response,
        }
    elif method == "multiagent":
        analysis = analysis or {}
        judge = analysis.get("llm_judge") or {}
        output = {
            "treatment_score": float(prediction_score),
            "confidence": judge.get("confidence"),
            "uncertainty": judge.get("uncertainty"),
            "grade_reason": judge.get("grade_reason") or "",
            "key_support": judge.get("key_support") or [],
            "key_conflict": judge.get("key_conflict") or [],
            "missing_evidence": judge.get("missing_evidence") or [],
            "reasoning_summary": (
                judge.get("reasoning_summary")
                or analysis.get("synthesis_explanation")
                or (analysis.get("synthesis") or {}).get("explanation")
                or ""
            ),
        }
    else:
        raise ValueError(f"Unsupported result method: {method}")

    if retention_note:
        output["retention_note"] = retention_note
    return output


def build_evidence_summary(
    *,
    method: str,
    analysis: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Summarize retrieved evidence without duplicating the full internal trace."""
    if method in {"direct", "cot"} or not analysis:
        return None

    expert_outputs = analysis.get("expert_outputs") or {}
    sources: dict[str, Any] = {}
    for source_name, output in expert_outputs.items():
        evidence = output.get("evidence") or []
        sources[str(source_name)] = {
            "status": output.get("status"),
            "evidence_count": len(evidence),
            "representative_claims": [
                item.get("claim") or ""
                for item in evidence[:3]
                if isinstance(item, Mapping)
            ],
        }

    graph = analysis.get("evidence_graph") or {}
    summary: dict[str, Any] = {
        "queried_sources": list(sources),
        "source_records": sources,
        "source_coverage": graph.get("coverage") or {},
        "supportive_evidence_count": graph.get("supportive_evidence"),
        "conflict_evidence_count": graph.get("risk_evidence"),
        "mean_confidence": graph.get("mean_confidence"),
        "conflict_level": graph.get("conflict_level"),
        "top_evidence": (graph.get("top_evidence") or [])[:6],
    }

    if method == "multiagent":
        planner_trace = []
        for step in analysis.get("trajectory") or []:
            planner = step.get("planner_output") or {}
            planner_trace.append(
                {
                    "round": step.get("round"),
                    "action": planner.get("next_action"),
                    "reason": planner.get("reason") or "",
                    "planner_question": planner.get("planner_question") or "",
                }
            )
        summary["planner_trace"] = planner_trace
    return summary


def build_result_record(
    *,
    index: int,
    sample_id: str,
    smiles: str,
    disease: str,
    drug_names: Sequence[str] | None,
    label: int,
    method: str,
    workflow: str,
    agent_version: str | None,
    prediction_score: float,
    prediction_binary: int,
    threshold: float,
    source_score_field: str,
    model_output: Mapping[str, Any],
    evidence_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build one record in the format written by both release and live runs."""
    return {
        "index": int(index),
        "sample_id": str(sample_id),
        "smiles": smiles,
        "disease": disease,
        "drug_names": list(drug_names or []),
        "label": int(label),
        "method": method,
        "workflow": workflow,
        "agent_version": agent_version,
        "prediction_score": float(prediction_score),
        "prediction_binary": int(prediction_binary),
        "threshold": float(threshold),
        "score_semantics": score_semantics(method),
        "source_score_field": source_score_field,
        "correct": int(prediction_binary) == int(label),
        "model_output": dict(model_output),
        "evidence_summary": dict(evidence_summary) if evidence_summary is not None else None,
    }


def build_run_payload(
    *,
    metrics: Mapping[str, Any],
    method: str,
    workflow: str,
    agent_version: str | None,
    threshold: float,
    split: str | None,
    results: Sequence[Mapping[str, Any]],
    description: str,
    component_removed: str | None,
    model_identifier: str,
    records_are_frozen: bool,
    provenance_kind: str,
    source_file: str,
    source_sha256: str,
    source_collection: str | None,
    execution_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete evaluation JSON document."""
    normalized_results = [dict(item) for item in results]
    positive_samples = sum(int(item["label"]) for item in normalized_results)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "metrics": {key: float(value) for key, value in metrics.items()},
        "method": method,
        "workflow": workflow,
        "agent_version": agent_version,
        "threshold": float(threshold),
        "split": split,
        "total_samples": len(normalized_results),
        "positive_samples": positive_samples,
        "negative_samples": len(normalized_results) - positive_samples,
        "run_metadata": {
            "description": description,
            "component_removed": component_removed,
            "model_identifier": model_identifier,
            "records_are_frozen": bool(records_are_frozen),
            "execution_config": dict(execution_config or {}),
        },
        "provenance": {
            "kind": provenance_kind,
            "source_file": source_file,
            "source_sha256": source_sha256,
            "source_collection": source_collection,
        },
        "results": normalized_results,
    }


def final_score_from_analysis(analysis: Mapping[str, Any]) -> tuple[float, str]:
    """Return the continuous final score and its stored field name."""
    candidates = (
        (analysis.get("llm_judge_probability"), "llm_judge_probability"),
        (analysis.get("argument_probability"), "argument_probability"),
        ((analysis.get("calibration") or {}).get("calibrated_probability"), "calibrated_probability"),
    )
    for value, field in candidates:
        if value is not None:
            return float(value), field
    raise ValueError("Multiagent analysis does not contain a final continuous score.")

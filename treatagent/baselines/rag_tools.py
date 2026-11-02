"""Fixed-retrieval tool layer for the paper's RAG+Tools baseline.

This module deliberately bypasses the TreatAgent planner, evidence agents,
candidate-level integration, and final reviewer. It reuses the same five local
biomedical tools, queries every tool once in a predefined order, and returns
their raw structured records for a single downstream LLM scoring prompt.
"""

from __future__ import annotations

from typing import Any

from treatagent.orchestration.orchestrator import TreatAgentOrchestrator


FIXED_TOOL_ORDER = ("DrugInfo", "DiseaseInfo", "DTI", "ADMET", "TrialPrior")


class FixedRAGToolRetriever:
    """Run the shared tools without any adaptive TreatAgent components."""

    def __init__(self, *, knowledge_cutoff_date: str | None = None) -> None:
        # The local orchestrator is used only as the shared tool runtime. Its
        # analyze/planner/integration/reviewer paths are never invoked here.
        self._tool_runtime = TreatAgentOrchestrator(
            model="local",
            agent_version="eg",
            generate_report=False,
            use_memory=False,
            knowledge_cutoff_date=knowledge_cutoff_date,
        )

    def retrieve(
        self,
        smiles: str,
        disease: str,
        *,
        sample_id: str | None = None,
    ) -> dict[str, Any]:
        outputs: dict[str, dict[str, Any]] = {}
        for tool_name in FIXED_TOOL_ORDER:
            try:
                output = self._tool_runtime.skill_registry.execute(tool_name, smiles, disease)
            except Exception as exc:  # keep the fixed procedure complete
                output = {
                    "expert": tool_name,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "evidence": [],
                }
            outputs[tool_name] = output

        evidence = [
            item
            for output in outputs.values()
            for item in (output.get("evidence") or [])
            if isinstance(item, dict)
        ]
        confidences = [
            float(item["confidence"])
            for item in evidence
            if isinstance(item.get("confidence"), (int, float))
        ]
        coverage = {
            name: len(outputs[name].get("evidence") or [])
            for name in FIXED_TOOL_ORDER
        }
        return {
            "sample_id": sample_id,
            "drug": smiles,
            "disease": disease,
            "agent_version": None,
            "retrieval_mode": "fixed_all_tools",
            "retrieval_order": list(FIXED_TOOL_ORDER),
            "adaptive_planner_enabled": False,
            "llm_planner_enabled": False,
            "llm_experts_enabled": False,
            "candidate_level_integration_enabled": False,
            "llm_judge_enabled": False,
            "expert_outputs": outputs,
            "evidence_graph": {
                "drug": smiles,
                "disease": disease,
                "coverage": coverage,
                "supportive_evidence": sum(item.get("impact") == "supportive" for item in evidence),
                "risk_evidence": sum(item.get("impact") == "risk" for item in evidence),
                "mean_confidence": (
                    sum(confidences) / len(confidences) if confidences else None
                ),
                "conflict_level": None,
                "top_evidence": [],
            },
        }

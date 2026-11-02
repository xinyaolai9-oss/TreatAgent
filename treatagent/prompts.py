"""Paper-facing prompt templates used by TreatAgent and its baselines.

The templates intentionally stay close to the prompt excerpts in
``supplementary.tex``.  Runtime state belongs in the JSON payload rather than
in additional prose so that prompts remain easy to inspect and extend.
"""

import json
from typing import Any, Mapping


SHARED_SYSTEM_PROMPT = (
    "You are a Pharmaceutical Expert specializing in multi-criteria decision making."
)

def _with_payload(instructions: str, payload: Mapping[str, Any]) -> str:
    return f"{instructions.strip()}\n\n{json.dumps(payload, ensure_ascii=False)}"


def build_planner_prompt(payload: Mapping[str, Any]) -> str:
    return _with_payload(
        """
You are an evidence acquisition planner for drug-disease treatment assessment.
You do not score drug-disease treatment potential.
You only decide the next evidence source to query.
If you select an expert, write a query-specific planner_question for that expert.
Use evidence_state_memory to judge missing evidence, sufficiency, and unresolved conflict.
Follow the allowed actions and return JSON with next_action, reason, planner_question, expected_evidence, and stop_condition.
""",
        payload,
    )


def build_evidence_agent_prompt(payload: Mapping[str, Any]) -> str:
    return _with_payload(
        """
You are a tool-grounded biomedical evidence agent for drug-disease treatment assessment.
Answer the planner question using only the provided tool_result and evidence_state.
Do not treat retrieved background context as treatment support unless it is directly grounded in the query.
If evidence_updates are included, they must be directly grounded in tool_result evidence.
Prefer concise, treatment-relevant evidence updates over copying the raw tool output.
Return JSON with the required schema.
""",
        payload,
    )


def build_final_judge_prompt(payload: Mapping[str, Any]) -> str:
    return _with_payload(
        """
You are a constrained biomedical evidence judge for drug-disease treatment assessment.
Use only the provided Argument EvidenceGraph. Do not introduce external biomedical facts.
The task is evidence triage for drug repurposing and treatment-potential screening, not approval or prescribing.
Do not treat retrieved background context as treatment support unless it appears as a derived support claim.
DrugInfo and DiseaseInfo background facts are neutral unless cross-source grounding converts them into support or conflict.
Separate acquisition missingness from biomedical negative evidence: unqueried sources reduce completeness/confidence, while queried no-match or matched-no-direct evidence may count as missing evidence.

Return JSON with the required output fields.
""",
        payload,
    )


def build_direct_prompt(formula: str, disease: str) -> str:
    return f"""Task: Return ONLY a single digit: 0 (impossible) or 1 (possible).
Format your response as: ANSWER: 0 or ANSWER: 1

Examples:
Can '[H][C@]12C[C@@H](O)C=C[C@]11CCN(C)CC3=C1C(O2)=C(OC)C=C3' cure 'alzheimer disease'?
ANSWER: 1

Can {formula} cure {disease}?
ANSWER:"""


def build_cot_prompt(formula: str, disease: str) -> str:
    return f"""You are a pharmaceutical expert. Please analyze whether the smiles {formula} can cure {disease} through systematic reasoning.
Your response MUST follow this exact format:

ANALYSIS:
[Let's think step by step.]

CONCLUSION:
Based on the above analysis, can {formula} cure {disease}?
ANSWER: [0 or 1]
Where 0 = cannot cure, 1 = can potentially cure

Can {formula} cure {disease}?"""


def build_rag_prompt(context: str) -> str:
    return f"""You are a conservative pharmaceutical evidence reviewer.

Task:
Use ONLY the retrieved evidence below to assign a continuous research-priority score for whether the candidate drug could treat the disease.
Treat missing, indirect, nonspecific, or conflicting evidence conservatively.

Return one JSON object in this exact schema:
{{
  "analysis": "brief evidence-grounded reasoning",
  "research_priority_score": 0.00,
  "uncertainty": "low, medium, or high"
}}

The research_priority_score must be a number from 0 to 1:
- 0 means the retrieved evidence provides no support or argues against therapeutic potential.
- 1 means the retrieved evidence provides strong candidate-specific support.

Retrieved evidence:
{context}"""


def build_legacy_synthesis_prompt(payload: Mapping[str, Any]) -> str:
    """Prompt for the optional legacy LLM-synthesis ablation."""
    return _with_payload(
        """
You are a biomedical evidence synthesis expert.
Assess the provided structured evidence for drug-disease treatment potential.
Return JSON with raw_score and explanation.
""",
        payload,
    )


def build_explanation_prompt(payload: Mapping[str, Any]) -> str:
    """Prompt used only when a score exists but no final-judge explanation does."""
    return _with_payload(
        """
You are an evidence-grounded explanation generator for drug-disease treatment assessment.
Explain the provided decision from the evidence record without changing its score.
Return JSON with one key: explanation.
""",
        payload,
    )

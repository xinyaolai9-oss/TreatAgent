import argparse
import json
import os
import re
import traceback
from datetime import datetime
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from treatagent.baselines import FixedRAGToolRetriever
from treatagent.config.baselines import get_response
from treatagent.orchestration.argument_graph_scorer import argument_factors_from_result
from treatagent.orchestration.orchestrator import TreatAgentOrchestrator
from treatagent.prompts import build_cot_prompt, build_direct_prompt, build_rag_prompt
from treatagent.result_schema import (
    RESULT_SCHEMA_VERSION,
    WORKFLOW_DESCRIPTIONS,
    build_evidence_summary,
    build_model_output,
    build_result_record,
    build_run_payload,
    final_score_from_analysis,
    sha256_file,
    workflow_for_method,
)
from treatagent.skills.trial_prior import configure_trial_prior
from treatagent.utils import build_sample_id


def load_json_data(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        print(f"Error loading JSON file: {exc}")
        return []


def predict_multiagent(
    formula,
    disease,
    model,
    agent_version="full",
    label=None,
    sample_id=None,
    threshold=None,
    generate_report=False,
    use_memory=False,
    knowledge_cutoff_date=None,
    drug_names=None,
    drug_identifiers=None,
    drug_inchikey=None,
):
    system = TreatAgentOrchestrator(
        model=model,
        agent_version=agent_version,
        generate_report=generate_report,
        use_memory=use_memory,
        knowledge_cutoff_date=knowledge_cutoff_date,
    )
    result = system.analyze(
        formula,
        disease,
        label=label,
        sample_id=sample_id,
        drug_names=drug_names,
        drug_identifiers=drug_identifiers,
        drug_inchikey=drug_inchikey,
    )

    normalized_version = str(agent_version).lower()
    judge = result.get("llm_judge") or {}
    use_llm_judge_score = (
        normalized_version == "full"
        and isinstance(judge, dict)
        and judge.get("treatment_score") is not None
    )
    use_arg_final_score = normalized_version in {"eg", "full"} and not use_llm_judge_score
    if use_llm_judge_score:
        argument_row = argument_factors_from_result(result)
        argument_factors = argument_row.get("factors") or {}
        final_probability = float(judge.get("treatment_score"))
        final_threshold = 0.2 if threshold is None else float(threshold)
        prediction_binary = 1.0 if final_probability >= final_threshold else 0.0
        result["argument_probability"] = round(float(argument_factors.get("raw_argument_score", 0.0)), 6)
        result["argument_prediction"] = 1 if result["argument_probability"] >= _resolve_arg_threshold(None) else 0
        result["argument_factors"] = argument_factors
        result["llm_judge_probability"] = round(final_probability, 6)
        result["llm_judge_prediction"] = int(prediction_binary)
        result["final_score_source"] = "llm_evidence_judge"
        result["final_threshold"] = final_threshold
    elif use_arg_final_score:
        argument_row = argument_factors_from_result(result)
        argument_factors = argument_row.get("factors") or {}
        final_probability = float(argument_factors.get("raw_argument_score", 0.0))
        final_threshold = _resolve_arg_threshold(threshold)
        prediction_binary = 1.0 if final_probability >= final_threshold else 0.0
        result["argument_probability"] = round(final_probability, 6)
        result["argument_prediction"] = int(prediction_binary)
        result["argument_factors"] = argument_factors
        result["final_score_source"] = "argument_graph"
        result["final_threshold"] = final_threshold
    else:
        calibrated_probability = result["calibration"]["calibrated_probability"]
        final_probability = calibrated_probability
        final_threshold = 0.5 if threshold is None else threshold
        prediction_binary = 1.0 if final_probability >= final_threshold else 0.0
        result["final_score_source"] = "llm_synthesis_calibration"
        result["final_threshold"] = final_threshold

    print(f"Raw score: {result['synthesis']['raw_score']:.4f}/10")
    print(f"Calibrated probability: {result['calibration']['calibrated_probability']:.4f}")
    if use_llm_judge_score:
        print(f"LLM judge probability: {final_probability:.4f}")
    if use_arg_final_score:
        print(f"ARG probability: {final_probability:.4f}")
    print(f"Final score source: {result['final_score_source']}")
    print(f"Decision threshold: {final_threshold:.4f}")
    return {
        "prediction_binary": prediction_binary,
        "analysis": result,
    }


def _resolve_arg_threshold(threshold):
    if threshold is not None:
        return float(threshold)
    raw = os.getenv("TREATAGENT_ARG_THRESHOLD", "0.36")
    try:
        return float(raw)
    except ValueError:
        return 0.36


def _effective_threshold(method, agent_version, threshold):
    if threshold is not None:
        return float(threshold)
    if method == "multiagent" and agent_version == "full":
        return 0.2
    if method == "multiagent" and agent_version == "eg":
        return _resolve_arg_threshold(None)
    if method == "rag":
        return 0.4
    return 0.5


def _extract_binary_answer(response_text):
    match = re.search(r"ANSWER:\s*([01])", response_text.upper())
    if match:
        return int(match.group(1))

    fallback_match = re.search(r"\b([01])\b", response_text)
    if fallback_match:
        return int(fallback_match.group(1))

    print("Warning: Could not extract valid score from response, defaulting to 0")
    return 0


def _extract_rag_score(response_text):
    """Parse the continuous score emitted by the protocol-matched RAG reviewer."""
    cleaned = response_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    object_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        try:
            score = float(payload.get("research_priority_score"))
        except (TypeError, ValueError):
            continue
        if 0.0 <= score <= 1.0:
            return (
                score,
                str(payload.get("analysis", "")).strip(),
                str(payload.get("uncertainty", "")).strip().lower(),
            )

    fallback = re.search(
        r"(?:RESEARCH_PRIORITY_SCORE|SCORE)\s*[:=]\s*(0(?:\.\d+)?|1(?:\.0+)?)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if fallback:
        return float(fallback.group(1)), "", ""
    raise ValueError("Could not extract a valid continuous RAG score in [0, 1].")


def predict_direct(formula, disease, model):
    prompt = build_direct_prompt(formula, disease)
    response = get_response(prompt, model)
    print("response: ", response)
    score = _extract_binary_answer(response.strip())
    print("direct score:", score)
    return float(score)


def predict_cot(formula, disease, model):
    prompt = build_cot_prompt(formula, disease)
    response = get_response(prompt, model)
    print("response: ", response)
    score = _extract_binary_answer(response.strip())
    print("direct score:", score)
    return float(score)


def _build_rag_context(analysis):
    evidence_graph = analysis.get("evidence_graph") or {}
    expert_outputs = analysis.get("expert_outputs") or {}
    lines = [
        f"Drug SMILES: {analysis.get('drug') or evidence_graph.get('drug')}",
        f"Disease: {analysis.get('disease') or evidence_graph.get('disease')}",
        "",
        "Retrieved evidence:",
    ]

    for expert_name in ["DrugInfo", "DiseaseInfo", "DTI", "ADMET", "TrialPrior"]:
        output = expert_outputs.get(expert_name) or {}
        status = output.get("status", "missing")
        lines.append(f"\n[{expert_name}] status={status}")
        evidence_items = output.get("evidence") or []
        if not evidence_items:
            lines.append("- No retrieved evidence.")
            continue
        for item in evidence_items[:8]:
            claim = str(item.get("claim", "")).strip()
            value = item.get("value")
            impact = item.get("impact")
            confidence = item.get("confidence")
            source = item.get("source")
            lines.append(
                f"- claim={claim}; value={value}; impact={impact}; confidence={confidence}; source={source}"
            )

    return "\n".join(lines)


def predict_rag(
    formula,
    disease,
    model,
    label=None,
    sample_id=None,
    threshold=None,
    knowledge_cutoff_date=None,
    drug_names=None,
    drug_identifiers=None,
    drug_inchikey=None,
):
    retriever = FixedRAGToolRetriever(
        knowledge_cutoff_date=knowledge_cutoff_date,
    )
    analysis = retriever.retrieve(
        formula,
        disease,
        sample_id=sample_id,
    )
    context = _build_rag_context(analysis)
    prompt = build_rag_prompt(context)
    response = get_response(prompt, model)
    print("response: ", response)
    score, score_analysis, uncertainty = _extract_rag_score(response)
    decision_threshold = 0.4 if threshold is None else float(threshold)
    prediction_binary = 1.0 if score >= decision_threshold else 0.0
    print("continuous rag score:", score)
    return {
        "prediction_score": float(score),
        "prediction_binary": prediction_binary,
        "score_analysis": score_analysis,
        "uncertainty": uncertainty,
        "analysis": analysis,
        "rag_context": context,
        "rag_response": response,
    }


def predict_therapeutic_potential(
    formula,
    disease,
    method="multiagent",
    model="gpt-4",
    agent_version="full",
    label=None,
    sample_id=None,
    threshold=None,
    generate_report=False,
    use_memory=False,
    knowledge_cutoff_date=None,
    drug_names=None,
    drug_identifiers=None,
    drug_inchikey=None,
):
    if method == "multiagent":
        return predict_multiagent(
            formula,
            disease,
            model,
            agent_version=agent_version,
            label=label,
            sample_id=sample_id,
            threshold=threshold,
            generate_report=generate_report,
            use_memory=use_memory,
            knowledge_cutoff_date=knowledge_cutoff_date,
            drug_names=drug_names,
            drug_identifiers=drug_identifiers,
            drug_inchikey=drug_inchikey,
        )
    if method == "direct":
        return predict_direct(formula, disease, model)
    if method == "cot":
        return predict_cot(formula, disease, model)
    if method == "rag":
        return predict_rag(
            formula,
            disease,
            model,
            label=label,
            sample_id=sample_id,
            threshold=threshold,
            knowledge_cutoff_date=knowledge_cutoff_date,
            drug_names=drug_names,
            drug_identifiers=drug_identifiers,
            drug_inchikey=drug_inchikey,
        )
    raise ValueError(f"Unsupported method: {method}")


def compute_metrics(y_true, y_pred):
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "f1": f1_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
    }


def save_checkpoint(results, y_true, y_pred, processed_indices, checkpoint_path):
    checkpoint_data = {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "results": results,
        "y_true": y_true,
        "y_pred": y_pred,
        "processed_indices": list(processed_indices),
        "timestamp": datetime.now().isoformat(),
        "total_processed": len(results),
    }
    try:
        with open(checkpoint_path, "w", encoding="utf-8") as handle:
            json.dump(checkpoint_data, handle, indent=2, ensure_ascii=False)
        print(f"Checkpoint saved: {len(results)} samples processed")
    except Exception as exc:
        print(f"Error saving checkpoint: {exc}")


def load_checkpoint(checkpoint_path):
    try:
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r", encoding="utf-8") as handle:
                checkpoint_data = json.load(handle)
            if checkpoint_data.get("result_schema_version") != RESULT_SCHEMA_VERSION:
                print("Ignoring checkpoint written with an incompatible result schema.")
                return [], [], [], set(), None
            print(f"Loaded checkpoint: {checkpoint_data['total_processed']} samples already processed")
            return (
                checkpoint_data["results"],
                checkpoint_data["y_true"],
                checkpoint_data["y_pred"],
                set(checkpoint_data["processed_indices"]),
                checkpoint_data["timestamp"],
            )
    except Exception as exc:
        print(f"Error loading checkpoint: {exc}")
    return [], [], [], set(), None


def get_checkpoint_path(args):
    checkpoint_dir = "checkpoints"
    os.makedirs(checkpoint_dir, exist_ok=True)
    json_base = os.path.splitext(os.path.basename(args.json_path))[0]
    checkpoint_name = f"checkpoint_{json_base}_{args.method}_{args.backbone}_{args.agent_version}.json"
    return os.path.join(checkpoint_dir, checkpoint_name)


def cleanup_checkpoint(checkpoint_path):
    try:
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            print(f"Checkpoint file removed: {checkpoint_path}")
    except Exception as exc:
        print(f"Warning: Could not remove checkpoint file: {exc}")


def build_parser():
    parser = argparse.ArgumentParser(description="Run TreatAgent predictions.")
    parser.add_argument(
        "--json_path",
        type=str,
        default="data/benchmark/splits/drug_disjoint_test.json",
        help="Path to JSON file with disease and SMILES data",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Threshold for binary classification. Defaults to 0.20 for the manuscript full workflow, 0.40 for continuous RAG, TREATAGENT_ARG_THRESHOLD/0.36 for eg, and 0.5 for binary baselines/ls.",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="multiagent",
        choices=["direct", "cot", "rag", "multiagent"],
        help="Prediction method to use",
    )
    parser.add_argument("--backbone", type=str, default="gpt-4", help="Backbone model. The manuscript used gpt-4; use --backbone local to disable LLM synthesis and run fully local multiagent inference.")
    parser.add_argument(
        "--agent_version",
        type=str,
        default="full",
        choices=["eg", "full", "ls"],
        help="TreatAgent version for multiagent runs: eg=ArgumentGraph fallback scorer, full=LLM planner plus EvidenceGraph LLM judge, ls=LLM synthesis scorer baseline.",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint if available")
    parser.add_argument("--save_every", type=int, default=10, help="Save checkpoint every N samples")
    parser.add_argument("--generate_report", action="store_true", help="Generate an interactive HTML report for each sample")
    parser.add_argument("--use_memory", action="store_true", help="Enable vector-memory retrieval and storage")
    parser.add_argument(
        "--knowledge_cutoff_date",
        type=str,
        default=None,
        help="Optional knowledge cutoff date (YYYY-MM-DD). KB records with later snapshot_date will be ignored.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.method in {"multiagent", "rag"}:
        try:
            prior_path = configure_trial_prior(input_path=args.json_path)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"TrialPrior mapping: {prior_path}")
    workflow = workflow_for_method(args.method)
    effective_threshold = _effective_threshold(args.method, args.agent_version, args.threshold)
    execution_config = {
        "method": args.method,
        "model_identifier": args.backbone,
        "threshold": effective_threshold,
    }

    print(f"model: {args.backbone}!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    data = load_json_data(args.json_path)
    if not data:
        print("No data loaded. Exiting.")
        return

    print(f"Loaded {len(data)} samples from {args.json_path}")
    print(f"Using method: {args.method}")
    if args.method == "multiagent":
        print(f"Using TreatAgent version: {args.agent_version}")

    checkpoint_path = get_checkpoint_path(args)
    y_true = []
    y_pred = []
    results = []
    processed_indices = set()

    if args.resume:
        results, y_true, y_pred, processed_indices, _ = load_checkpoint(checkpoint_path)
        if processed_indices:
            print(f"Resuming from previous run - {len(processed_indices)} samples already processed")

    total_samples = len(data)

    for idx, sample in enumerate(data):
        if idx in processed_indices:
            continue

        print(f"\nProcessing sample {idx + 1}/{total_samples}...")

        smiles = str(
            sample.get("smiles")
            or sample.get("canonical_smiles")
            or sample.get("example_smiles")
            or ""
        ).strip()
        disease = str(
            sample.get("disease")
            or sample.get("normalized_disease")
            or sample.get("example_disease")
            or ""
        ).strip()
        label = sample.get("label", 0)
        # Fair comparison boundary: every method receives only SMILES and disease.
        # Drug names and inherited identifiers remain benchmark metadata and are
        # deliberately excluded from retrieval and prediction.
        drug_names = []
        drug_identifiers = []
        drug_inchikey = None

        try:
            sample_id = sample.get("sample_id") or sample.get("pair_id") or build_sample_id(smiles, disease)
            prediction_output = predict_therapeutic_potential(
                smiles,
                disease,
                method=args.method,
                model=args.backbone,
                agent_version=args.agent_version,
                label=label,
                sample_id=sample_id,
                threshold=args.threshold,
                generate_report=args.generate_report,
                use_memory=args.use_memory,
                knowledge_cutoff_date=args.knowledge_cutoff_date,
                drug_names=drug_names,
                drug_identifiers=drug_identifiers,
                drug_inchikey=drug_inchikey,
            )

            rag_context = None
            rag_response = None
            rag_score_analysis = None
            rag_uncertainty = None
            if args.method == "multiagent":
                analysis = prediction_output["analysis"]
                execution_config.update(
                    {
                        "agent_version": analysis.get("agent_version"),
                        "llm_planner_enabled": analysis.get("llm_planner_enabled"),
                        "llm_evidence_agents_enabled": analysis.get("llm_experts_enabled"),
                        "llm_evidence_agent_names": analysis.get("llm_expert_names") or [],
                        "llm_final_reviewer_enabled": analysis.get("llm_judge_enabled"),
                        "planner_budget": analysis.get("planner_budget"),
                        "max_rounds": analysis.get("max_rounds"),
                    }
                )
                prediction_score, source_score_field = final_score_from_analysis(analysis)
                prediction_binary = int(prediction_output["prediction_binary"])
            elif args.method == "rag":
                prediction_score = float(prediction_output["prediction_score"])
                prediction_binary = int(prediction_output["prediction_binary"])
                source_score_field = "prediction_score"
                analysis = prediction_output["analysis"]
                rag_context = prediction_output.get("rag_context")
                rag_response = prediction_output.get("rag_response")
                rag_score_analysis = prediction_output.get("score_analysis")
                rag_uncertainty = prediction_output.get("uncertainty")
                execution_config.update(
                    {
                        "retrieval_mode": analysis.get("retrieval_mode"),
                        "retrieval_order": analysis.get("retrieval_order") or [],
                        "adaptive_planner_enabled": False,
                        "llm_evidence_agents_enabled": False,
                        "candidate_level_integration_enabled": False,
                        "llm_final_reviewer_enabled": False,
                    }
                )
            else:
                prediction_score = float(prediction_output)
                prediction_binary = int(prediction_score)
                source_score_field = "prediction_binary"
                analysis = None

            y_true.append(label)
            y_pred.append(prediction_binary)

            retention_note = None
            if args.method == "direct":
                retention_note = "This CLI result retains the parsed answer, not the raw model response."
            elif args.method == "cot":
                retention_note = "This CLI result retains the parsed answer, not intermediate free-text reasoning."
            result_entry = build_result_record(
                index=idx + 1,
                sample_id=(analysis or {}).get("sample_id", sample_id),
                smiles=smiles,
                disease=disease,
                drug_names=drug_names,
                label=label,
                method=args.method,
                workflow=workflow,
                agent_version=(analysis or {}).get("agent_version", args.agent_version)
                if args.method == "multiagent"
                else None,
                prediction_score=prediction_score,
                prediction_binary=prediction_binary,
                threshold=effective_threshold,
                source_score_field=source_score_field,
                model_output=build_model_output(
                    method=args.method,
                    prediction_score=prediction_score,
                    prediction_binary=prediction_binary,
                    analysis=analysis,
                    rag_score_analysis=rag_score_analysis,
                    rag_uncertainty=rag_uncertainty,
                    raw_response=rag_response,
                    retention_note=retention_note,
                ),
                evidence_summary=build_evidence_summary(method=args.method, analysis=analysis),
            )
            results.append(result_entry)
            processed_indices.add(idx)

            print(f"  SMILES: {smiles[:50]}...")
            print(f"  Sample ID: {sample_id}")
            print(f"  Disease: {disease}")
            if args.method == "rag":
                print(
                    f"  Label: {label}, Score: {float(prediction_score):.4f}, "
                    f"Predicted: {prediction_binary} (Method: {args.method})"
                )
            else:
                print(f"  Label: {label}, Predicted: {prediction_binary} (Method: {args.method})")
            if args.method == "multiagent" and analysis is not None:
                print(f"  Raw score: {analysis['synthesis']['raw_score']:.4f}/10")
                print(f"  Synthesis source: {analysis['synthesis'].get('synthesis_source')}")
                print(f"  Explanation source: {analysis['synthesis'].get('explanation_source')}")
                print(f"  Calibrated probability: {analysis['calibration']['calibrated_probability']:.4f}")
                if analysis.get("argument_probability") is not None:
                    print(f"  ARG probability: {analysis['argument_probability']:.4f}")
                if analysis.get("llm_judge_probability") is not None:
                    print(f"  LLM judge probability: {analysis['llm_judge_probability']:.4f}")
                print(f"  Final score source: {analysis.get('final_score_source')}")
                print(f"  Group scores: {analysis['synthesis'].get('group_scores')}")
                print(f"  Similar memory cases: {analysis['memory_similar_cases']}")
                print(f"  Memory enabled: {analysis['memory_enabled']}")
                if analysis["memory_init_error"]:
                    print(f"  Memory init error: {analysis['memory_init_error']}")
                if analysis["report_path"]:
                    print(f"  Report: {analysis['report_path']}")

            if (idx + 1) % args.save_every == 0:
                save_checkpoint(results, y_true, y_pred, processed_indices, checkpoint_path)

        except KeyboardInterrupt:
            print("\n\nProcessing interrupted by user. Saving checkpoint...")
            save_checkpoint(results, y_true, y_pred, processed_indices, checkpoint_path)
            print("Checkpoint saved. You can resume later with --resume flag.")
            return
        except Exception as exc:
            print(f"Error processing sample {idx + 1}: {repr(exc)}")
            traceback.print_exc()
            continue

    if y_true and y_pred:
        metrics = compute_metrics(y_true, y_pred)

        print("\n" + "=" * 50)
        print("EVALUATION RESULTS")
        print("=" * 50)
        print(f"Method: {args.method}")
        if args.method == "multiagent":
            print(f"TreatAgent version: {args.agent_version}")
        print(f"Total samples processed: {len(y_true)}")
        print(f"Positive samples: {sum(y_true)}")
        print(f"Negative samples: {len(y_true) - sum(y_true)}")
        print(f"Threshold: {effective_threshold}")
        print()
        print(f"Accuracy:  {metrics['accuracy']:.4f}")
        print(f"F1 Score:  {metrics['f1']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print("=" * 50)

        results_dir = f"results/{args.backbone}"
        os.makedirs(results_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_suffix = f"_{args.agent_version}" if args.method == "multiagent" else ""
        output_file = f"{results_dir}/results_{args.method}{version_suffix}_{timestamp}.json"
        source_path = Path(args.json_path).resolve()
        payload = build_run_payload(
            metrics=metrics,
            method=args.method,
            workflow=workflow,
            agent_version=args.agent_version if args.method == "multiagent" else None,
            threshold=effective_threshold,
            split=source_path.stem,
            results=results,
            description=WORKFLOW_DESCRIPTIONS[workflow],
            component_removed=None,
            model_identifier=args.backbone,
            records_are_frozen=False,
            provenance_kind="live_run",
            source_file=str(source_path),
            source_sha256=sha256_file(source_path),
            source_collection=None,
            execution_config=execution_config,
        )
        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print(f"\nDetailed results saved to: {output_file}")
        cleanup_checkpoint(checkpoint_path)
    else:
        print("No samples were processed successfully.")

    print(f"\nProcessing completed. Total samples processed: {len(results)}")


if __name__ == "__main__":
    main()

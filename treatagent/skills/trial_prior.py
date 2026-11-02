import json
import os
from pathlib import Path

from .knowledge_common import _build_disease_variants, _jaccard_similarity, _normalize_disease_name, difflib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRIAL_PRIOR_DIR = PROJECT_ROOT / "data" / "trial_prior" / "trial_priors"
TRIAL_PRIOR_SPLIT_PATHS = {
    "drug_disjoint": TRIAL_PRIOR_DIR / "drug_disjoint.json",
    "dd": TRIAL_PRIOR_DIR / "drug_disjoint.json",
    "submission_date_separated": TRIAL_PRIOR_DIR / "submission_date_separated.json",
    "temporal_submit": TRIAL_PRIOR_DIR / "submission_date_separated.json",
    "ss": TRIAL_PRIOR_DIR / "submission_date_separated.json",
}

_active_success_ratio_path = None
_disease_success_ratio = None
_normalized_success_ratio = None


def _normalize_split_name(value):
    return str(value or "").strip().lower().replace("-", "_")


def infer_trial_prior_split(input_path):
    """Infer the paper split from a benchmark input filename.

    This intentionally recognizes only the two reported evaluation protocols.
    Random and older temporal files must not silently borrow either prior.
    """
    name = Path(input_path).name.lower().replace("-", "_")
    if "drug_disjoint" in name:
        return "drug_disjoint"
    if "temporal_submit" in name or "submission_date_separated" in name:
        return "submission_date_separated"
    return None


def _resolve_success_ratio_path(split_name=None, input_path=None):
    explicit_path = os.getenv("TREATAGENT_TRIAL_PRIOR_PATH", "").strip()
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    split_name = _normalize_split_name(
        split_name or os.getenv("TREATAGENT_TRIAL_PRIOR_SPLIT", "")
    )
    if not split_name and input_path:
        split_name = infer_trial_prior_split(input_path)
    if split_name:
        try:
            return TRIAL_PRIOR_SPLIT_PATHS[split_name]
        except KeyError as exc:
            allowed = ", ".join(sorted(TRIAL_PRIOR_SPLIT_PATHS))
            raise ValueError(
                f"Unsupported TREATAGENT_TRIAL_PRIOR_SPLIT={split_name!r}; use one of: {allowed}"
            ) from exc
    raise RuntimeError(
        "TrialPrior requires a training-partition mapping. Use a DD/SS benchmark "
        "input filename, set TREATAGENT_TRIAL_PRIOR_SPLIT to drug_disjoint or "
        "submission_date_separated, or set TREATAGENT_TRIAL_PRIOR_PATH explicitly."
    )


def configure_trial_prior(*, split_name=None, input_path=None):
    """Select and load a leakage-safe TrialPrior mapping for this process."""
    global _active_success_ratio_path, _disease_success_ratio, _normalized_success_ratio
    path = _resolve_success_ratio_path(split_name=split_name, input_path=input_path)
    if not path.is_file():
        raise FileNotFoundError(f"TrialPrior mapping not found: {path}")
    if _active_success_ratio_path == path and _disease_success_ratio is not None:
        return path
    with path.open("r", encoding="utf-8") as handle:
        mapping = json.load(handle)
    _active_success_ratio_path = path
    _disease_success_ratio = mapping
    _normalized_success_ratio = {
        _normalize_disease_name(name): value
        for name, value in mapping.items()
        if _normalize_disease_name(name)
    }
    return path


def _ensure_trial_prior_loaded():
    if _disease_success_ratio is None:
        configure_trial_prior()
    return _disease_success_ratio, _normalized_success_ratio


def get_trial_prior(disease_name):
    disease_success_ratio, normalized_success_ratio = _ensure_trial_prior_loaded()
    if disease_name in disease_success_ratio:
        return {
            "success_rate": float(disease_success_ratio[disease_name]),
            "matched_disease": disease_name,
            "matched_by": "exact",
            "match_score": 1.0,
        }
    for variant in _build_disease_variants(disease_name):
        if variant in normalized_success_ratio:
            return {
                "success_rate": float(normalized_success_ratio[variant]),
                "matched_disease": variant,
                "matched_by": "normalized",
                "match_score": 0.98,
            }

    best_key = None
    best_score = 0.0
    for variant in _build_disease_variants(disease_name):
        for candidate in normalized_success_ratio:
            jaccard = _jaccard_similarity(variant, candidate)
            if jaccard < 0.35:
                continue
            ratio = difflib.SequenceMatcher(None, variant, candidate).ratio()
            score = max(jaccard, ratio)
            if variant in candidate or candidate in variant:
                score += 0.08
            if score > best_score:
                best_score = score
                best_key = candidate
    if best_key is not None and best_score >= 0.72:
        return {
            "success_rate": float(normalized_success_ratio[best_key]),
            "matched_disease": best_key,
            "matched_by": "fuzzy",
            "match_score": round(min(best_score, 1.0), 4),
        }
    return None


def get_trial_prior_score(disease_name):
    prior = get_trial_prior(disease_name)
    if prior is None:
        return None
    return prior["success_rate"]

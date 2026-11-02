from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rdkit import Chem, RDLogger

from .knowledge_common import DRUGINFO_PATH, _jaccard_similarity, _parse_snapshot_date


RDLogger.DisableLog("rdApp.warning")
RDLogger.DisableLog("rdApp.error")


class DrugInfoExpert:
    """Retrieve DrugCentral evidence using only the supplied molecular structure.

    ``drug_names``, external identifiers, and caller-supplied InChIKeys remain in
    the public signatures for backward compatibility, but they are deliberately
    ignored. Every lookup key is derived from ``smiles`` with the local RDKit
    version so all evaluated methods have the same candidate input boundary.
    """

    _cache_by_path: Dict[str, Dict[str, Any]] = {}

    def __init__(self, druginfo_path: Optional[Path] = None, knowledge_cutoff_date: Optional[str] = None):
        self.druginfo_path = Path(druginfo_path or DRUGINFO_PATH)
        self.knowledge_cutoff_date = _parse_snapshot_date(knowledge_cutoff_date)
        cache_key = str(self.druginfo_path.resolve())
        if cache_key not in self._cache_by_path:
            self._cache_by_path[cache_key] = self._load_cache()
        cache = self._cache_by_path[cache_key]
        self._records: List[Dict[str, Any]] = cache["records"]
        self._canonical_smiles_index: Dict[str, List[Dict[str, Any]]] = cache["canonical_smiles"]
        self._inchikey_index: Dict[str, List[Dict[str, Any]]] = cache["inchikey"]
        self._connectivity_index: Dict[str, List[Dict[str, Any]]] = cache["connectivity"]
        self._parent_connectivity_index: Dict[str, List[Dict[str, Any]]] = cache["parent_connectivity"]

    def _load_cache(self) -> Dict[str, Any]:
        records: List[Dict[str, Any]] = []
        canonical_smiles_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        inchikey_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        connectivity_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        parent_connectivity_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        if not self.druginfo_path.exists():
            return {
                "records": records,
                "canonical_smiles": canonical_smiles_index,
                "inchikey": inchikey_index,
                "connectivity": connectivity_index,
                "parent_connectivity": parent_connectivity_index,
            }

        with self.druginfo_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                signature = _structure_signature(record.get("canonical_smiles"))
                record["_rdkit_structure"] = signature
                records.append(record)
                if not signature["valid"]:
                    continue
                _append_unique(canonical_smiles_index, signature["canonical_smiles"], record)
                _append_unique(inchikey_index, signature["inchikey"], record)
                _append_unique(connectivity_index, signature["connectivity"], record)
                _append_unique(parent_connectivity_index, signature["parent_connectivity"], record)

        return {
            "records": records,
            "canonical_smiles": canonical_smiles_index,
            "inchikey": inchikey_index,
            "connectivity": connectivity_index,
            "parent_connectivity": parent_connectivity_index,
        }

    def _record_allowed(self, record: Dict[str, Any]) -> bool:
        if self.knowledge_cutoff_date is None:
            return True
        record_date = _parse_snapshot_date(record.get("snapshot_date"))
        if record_date is None:
            return True
        return record_date <= self.knowledge_cutoff_date

    def _allowed_candidates(self, records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if not self._record_allowed(record):
                continue
            record_id = str(record.get("drugcentral_id") or id(record))
            unique.setdefault(record_id, record)
        return sorted(unique.values(), key=lambda item: _record_sort_key(item.get("drugcentral_id")))

    def _lookup_result(self, smiles: str) -> Dict[str, Any]:
        signature = _structure_signature(smiles)
        if not signature["valid"]:
            return _lookup_payload(None, "invalid_smiles", 0.0, [], signature)

        tiers = [
            (
                "canonical_smiles",
                1.0,
                self._canonical_smiles_index.get(signature["canonical_smiles"], []),
            ),
            ("inchikey", 1.0, self._inchikey_index.get(signature["inchikey"], [])),
            (
                "connectivity_relaxed",
                0.80,
                self._connectivity_index.get(signature["connectivity"], []),
            ),
        ]
        if signature["fragment_count"] > 1 and signature["parent_connectivity"]:
            tiers.append(
                (
                    "parent_connectivity_relaxed",
                    0.75,
                    self._parent_connectivity_index.get(signature["parent_connectivity"], []),
                )
            )

        for method, score, raw_candidates in tiers:
            candidates = self._allowed_candidates(raw_candidates)
            if not candidates:
                continue
            if len(candidates) > 1:
                return _lookup_payload(
                    None,
                    f"ambiguous_{method}",
                    0.0,
                    candidates,
                    signature,
                )
            return _lookup_payload(candidates[0], method, score, candidates, signature)

        return _lookup_payload(None, "unmatched", 0.0, [], signature)

    def lookup(
        self,
        smiles: str,
        drug_names: Optional[Iterable[str]] = None,
        identifiers: Optional[Iterable[Any]] = None,
        inchikey: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        # Auxiliary identity fields are intentionally ignored. See class docstring.
        del drug_names, identifiers, inchikey
        result = self._lookup_result(smiles)
        return result["record"], result["matched_by"], result["match_score"]

    def analyze(
        self,
        smiles: str,
        disease: str,
        drug_names: Optional[Iterable[str]] = None,
        identifiers: Optional[Iterable[Any]] = None,
        inchikey: Optional[str] = None,
    ) -> Dict[str, Any]:
        ignored_auxiliary_inputs = bool(list(drug_names or [])) or bool(list(identifiers or [])) or bool(inchikey)
        result = self._lookup_result(smiles)
        record = result["record"]
        matched_by = result["matched_by"]
        match_score = result["match_score"]
        signature = result["signature"]

        if record is None:
            return {
                "expert": "DrugInfo",
                "status": "no_data",
                "raw_data": {
                    "lookup_input": "smiles_only",
                    "query_smiles": smiles,
                    "canonical_smiles": signature["canonical_smiles"],
                    "derived_inchikey": signature["inchikey"],
                    "derived_connectivity": signature["connectivity"],
                    "fragment_count": signature["fragment_count"],
                    "matched_by": matched_by,
                    "match_score": match_score,
                    "candidate_drugcentral_ids": result["candidate_ids"],
                    "ignored_auxiliary_inputs": ignored_auxiliary_inputs,
                },
                "evidence": [],
            }

        evidence: List[Dict[str, Any]] = []
        drug_name = record.get("drug_name") or "This molecule"
        approvals = record.get("approval", [])
        indications = record.get("known_indications", [])
        targets = record.get("known_targets", [])
        classes = record.get("pharmacologic_classes", [])
        match_metadata = {
            "matched_by": matched_by,
            "match_score": match_score,
            "drugcentral_id": record.get("drugcentral_id"),
            "drug_name": record.get("drug_name"),
            "snapshot_date": record.get("snapshot_date"),
        }

        if approvals:
            latest_approval = approvals[-1]
            evidence.append(
                self._evidence(
                    category="drug_identity",
                    claim=f"DrugCentral records {drug_name} as an approved or clinically annotated molecule.",
                    value=0.72,
                    impact="neutral",
                    confidence=0.78,
                    metadata={
                        **match_metadata,
                        "approval_date": latest_approval.get("approval_date"),
                        "agency": latest_approval.get("agency"),
                    },
                )
            )

        best_indication = None
        best_similarity = 0.0
        for item in indications:
            disease_name = item.get("disease_name") or ""
            similarity = _jaccard_similarity(disease, disease_name)
            if similarity > best_similarity:
                best_similarity = similarity
                best_indication = item

        if best_indication is not None and best_similarity >= 0.25:
            relationship = (best_indication.get("relationship") or "indication").lower()
            if relationship == "contraindication":
                evidence.append(
                    self._evidence(
                        category="drug_history",
                        claim=(
                            f"DrugCentral links {drug_name} to a contraindication profile overlapping "
                            f"with {best_indication.get('disease_name')}."
                        ),
                        value=min(1.0, 0.55 + best_similarity * 0.35),
                        impact="risk",
                        confidence=min(0.92, 0.62 + best_similarity * 0.28),
                        metadata={
                            **best_indication,
                            **match_metadata,
                            "indication_similarity": round(best_similarity, 4),
                        },
                    )
                )
            else:
                evidence.append(
                    self._evidence(
                        category="drug_history",
                        claim=(
                            f"DrugCentral reports a disease indication overlap between {drug_name} "
                            f"and {best_indication.get('disease_name')}."
                        ),
                        value=min(1.0, 0.6 + best_similarity * 0.3),
                        impact="supportive",
                        confidence=min(0.94, 0.65 + best_similarity * 0.25),
                        metadata={
                            **best_indication,
                            **match_metadata,
                            "indication_similarity": round(best_similarity, 4),
                        },
                    )
                )

        for item in targets[:3]:
            target_name = item.get("target_gene") or item.get("target_name")
            if not target_name:
                continue
            evidence.append(
                self._evidence(
                    category="mechanism_prior",
                    claim=f"DrugCentral annotates {drug_name} with target or mechanism prior on {target_name}.",
                    value=0.62 if item.get("moa") else 0.55,
                    impact="neutral",
                    confidence=0.68 if item.get("moa") else 0.6,
                    metadata={**item, **match_metadata},
                )
            )

        for item in classes[:2]:
            name = item.get("name")
            if not name:
                continue
            evidence.append(
                self._evidence(
                    category="drug_class",
                    claim=f"DrugCentral classifies {drug_name} under pharmacologic class {name}.",
                    value=0.55,
                    impact="neutral",
                    confidence=0.58,
                    metadata={**item, **match_metadata},
                )
            )

        return {
            "expert": "DrugInfo",
            "status": "ok" if evidence else "partial",
            "raw_data": {
                "lookup_input": "smiles_only",
                "query_smiles": smiles,
                "canonical_smiles": signature["canonical_smiles"],
                "derived_inchikey": signature["inchikey"],
                "derived_connectivity": signature["connectivity"],
                "fragment_count": signature["fragment_count"],
                "drug_name": record.get("drug_name"),
                "matched_by": matched_by,
                "match_score": match_score,
                "candidate_drugcentral_ids": result["candidate_ids"],
                "ignored_auxiliary_inputs": ignored_auxiliary_inputs,
                "identifiers": record.get("identifiers", [])[:10],
                "approvals": approvals[:2],
                "best_indication_overlap": best_indication,
                "best_indication_similarity": round(best_similarity, 4),
            },
            "record": {
                "drugcentral_id": record.get("drugcentral_id"),
                "drug_name": record.get("drug_name"),
                "snapshot_date": record.get("snapshot_date"),
            },
            "evidence": evidence,
        }

    def _evidence(
        self,
        category: str,
        claim: str,
        value: float,
        impact: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "expert": "DrugInfo",
            "category": category,
            "claim": claim,
            "value": round(max(0.0, min(1.0, value)), 4),
            "impact": impact,
            "confidence": round(max(0.5, min(0.95, confidence)), 4),
            "source": "DrugCentral snapshot",
            "metadata": metadata or {},
        }


def _record_sort_key(value: Any) -> Tuple[int, str]:
    text = str(value or "")
    try:
        return int(text), text
    except ValueError:
        return 10**12, text


def _append_unique(
    index: Dict[str, List[Dict[str, Any]]],
    key: str,
    record: Dict[str, Any],
) -> None:
    if not key:
        return
    record_id = str(record.get("drugcentral_id"))
    if any(str(item.get("drugcentral_id")) == record_id for item in index[key]):
        return
    index[key].append(record)


def _inchi_key(mol: Chem.Mol) -> str:
    try:
        return Chem.MolToInchiKey(mol)
    except Exception:
        return ""


def _parent_fragment(fragments: Tuple[Chem.Mol, ...]) -> Optional[Chem.Mol]:
    if len(fragments) <= 1:
        return fragments[0] if fragments else None

    organic = [
        fragment
        for fragment in fragments
        if any(atom.GetAtomicNum() == 6 for atom in fragment.GetAtoms())
    ]
    if not organic:
        return None
    organic.sort(key=lambda item: (item.GetNumHeavyAtoms(), item.GetNumAtoms()), reverse=True)
    if len(organic) == 1:
        return organic[0]

    largest = organic[0]
    second = organic[1]
    if second.GetNumHeavyAtoms() <= 8 and largest.GetNumHeavyAtoms() >= 2 * second.GetNumHeavyAtoms():
        return largest
    return None


def _structure_signature(smiles: Any) -> Dict[str, Any]:
    result = {
        "valid": False,
        "canonical_smiles": "",
        "inchikey": "",
        "connectivity": "",
        "fragment_count": 0,
        "parent_connectivity": "",
    }
    if smiles is None or not str(smiles).strip():
        return result
    mol = Chem.MolFromSmiles(str(smiles).strip())
    if mol is None:
        return result

    result["valid"] = True
    result["canonical_smiles"] = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    result["inchikey"] = _inchi_key(mol)
    if result["inchikey"]:
        result["connectivity"] = result["inchikey"].split("-", 1)[0]

    fragments = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    result["fragment_count"] = len(fragments)
    parent = _parent_fragment(fragments)
    if parent is not None:
        parent_key = _inchi_key(parent)
        if parent_key:
            result["parent_connectivity"] = parent_key.split("-", 1)[0]
    return result


def _lookup_payload(
    record: Optional[Dict[str, Any]],
    matched_by: str,
    match_score: float,
    candidates: Iterable[Dict[str, Any]],
    signature: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "record": record,
        "matched_by": matched_by,
        "match_score": match_score,
        "candidate_ids": [str(item.get("drugcentral_id")) for item in candidates],
        "signature": signature,
    }

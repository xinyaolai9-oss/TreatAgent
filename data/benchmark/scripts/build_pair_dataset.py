#!/usr/bin/env python3
"""Build the canonical pair-level TreatAgent benchmark from raw_data.csv."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "data" / "benchmark"
DEFAULT_INPUT = BENCHMARK / "raw_data.csv"
DEFAULT_OUTPUT = BENCHMARK / "processed" / "pair_level_dataset.json"
DEFAULT_STATS = BENCHMARK / "processed" / "build_stats.json"
BAD_DISEASE_TOKENS = [",", "-", "'", ";", ":", "(", ")", "[", "]", "{", "}", "<", ">", "/", "\\"]


def load_rdkit():
    try:
        from rdkit import Chem  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit("RDKit is required to build the benchmark.") from exc
    return Chem


def parse_list(value: str):
    if not value:
        return []
    parsed = ast.literal_eval(value)
    return parsed if isinstance(parsed, list) else []


def clean_disease(disease: str) -> bool:
    normalized = disease.lower().strip()
    return (
        normalized != "healthy"
        and not any(token in disease for token in BAD_DISEASE_TOKENS)
        and not any(char.isdigit() for char in disease)
    )


def normalize_disease(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip().lower())
    aliases = {
        "hiv infections": "hiv infection",
        "alzheimer disease": "alzheimer's disease",
        "neoplasms": "cancer",
    }
    return aliases.get(normalized, normalized)


def extract_rows(input_csv: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    stats = {
        "raw_rows": 0,
        "parse_errors": 0,
        "single_disease_single_smiles_rows": 0,
        "filtered_disease_rows": 0,
        "kept_rows": 0,
        "label_counts": {"0": 0, "1": 0},
    }
    with input_csv.open("r", encoding="utf-8", newline="") as handle:
        for row_id, row in enumerate(csv.DictReader(handle)):
            stats["raw_rows"] += 1
            try:
                diseases = parse_list(row.get("diseases", ""))
                smiles_values = parse_list(row.get("smiless", ""))
                drugs = parse_list(row.get("drugs", ""))
                icdcodes = parse_list(row.get("icdcodes", ""))
            except (ValueError, SyntaxError):
                stats["parse_errors"] += 1
                continue
            if len(diseases) != 1 or len(smiles_values) != 1:
                continue
            stats["single_disease_single_smiles_rows"] += 1
            disease = str(diseases[0]).strip()
            if not clean_disease(disease):
                stats["filtered_disease_rows"] += 1
                continue
            label = int(row["label"])
            rows.append({
                "source_row_id": row_id,
                "nctid": row.get("nctid", "").strip(),
                "status": row.get("status", "").strip(),
                "why_stop": row.get("why_stop", "").strip(),
                "label": label,
                "phase": row.get("phase", "").strip(),
                "disease": disease,
                "icdcodes": icdcodes,
                "drug": str(drugs[0]).strip() if len(drugs) == 1 else None,
                "smiles": str(smiles_values[0]).strip(),
            })
            stats["kept_rows"] += 1
            stats["label_counts"][str(label)] += 1
    return rows, stats


def canonical_pairs(rows: list[dict]) -> tuple[list[dict], dict]:
    chem = load_rdkit()
    canonicalized: list[dict] = []
    invalid_count = 0
    for item in rows:
        molecule = chem.MolFromSmiles(item["smiles"])
        if molecule is None:
            invalid_count += 1
            continue
        enriched = dict(item)
        enriched["normalized_disease"] = normalize_disease(item["disease"])
        enriched["canonical_smiles"] = chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
        enriched["canonicalization_status"] = "ok"
        canonicalized.append(enriched)

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in canonicalized:
        grouped[(item["canonical_smiles"], item["normalized_disease"])].append(item)

    pair_rows: list[dict] = []
    conflict_count = 0
    for pair_id, ((smiles, disease), items) in enumerate(sorted(grouped.items())):
        labels = {int(item["label"]) for item in items}
        if len(labels) > 1:
            conflict_count += 1
            continue
        nctids = sorted({item["nctid"] for item in items if item.get("nctid")})
        pair_rows.append({
            "pair_id": f"PAIR-{pair_id:06d}",
            "label": labels.pop(),
            "canonical_smiles": smiles,
            "normalized_disease": disease,
            "example_smiles": items[0]["smiles"],
            "example_disease": items[0]["disease"],
            "drugs": sorted({item["drug"] for item in items if item.get("drug")}),
            "nctids": nctids,
            "phases": sorted({item["phase"] for item in items if item.get("phase")}),
            "statuses": sorted({item["status"] for item in items if item.get("status")}),
            "source_row_ids": sorted({item["source_row_id"] for item in items}),
            "trial_count": len(nctids),
            "record_count": len(items),
        })

    stats = {
        "input_rows": len(rows),
        "valid_canonical_smiles_rows": len(canonicalized),
        "invalid_smiles_rows": invalid_count,
        "unique_pair_candidates": len(grouped),
        "pair_rows": len(pair_rows),
        "conflict_pairs_removed": conflict_count,
        "label_counts": dict(Counter(str(row["label"]) for row in pair_rows)),
        "unique_drugs": len({row["canonical_smiles"] for row in pair_rows}),
        "unique_diseases": len({row["normalized_disease"] for row in pair_rows}),
    }
    return pair_rows, stats


def build(input_csv: Path, output_json: Path, stats_json: Path) -> None:
    extracted, extraction_stats = extract_rows(input_csv)
    pairs, pair_stats = canonical_pairs(extracted)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_bytes(json.dumps(pairs, indent=2, ensure_ascii=False).encode("utf-8"))
    stats_json.write_bytes(
        json.dumps({"extraction": extraction_stats, "pair_dataset": pair_stats}, indent=2, ensure_ascii=False).encode("utf-8")
    )
    print(f"Wrote {len(pairs)} canonical pairs to {output_json}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output_json", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats_json", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    build(args.input_csv, args.output_json, args.stats_json)


if __name__ == "__main__":
    main()

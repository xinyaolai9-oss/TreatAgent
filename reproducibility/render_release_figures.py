#!/usr/bin/env python3
"""Render data-level reproductions of manuscript Figures 2--4."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def figure2(output: Path) -> None:
    dd = json.loads((ROOT / "data/benchmark/splits/drug_disjoint_test.json").read_text(encoding="utf-8"))
    ss_parts = {
        name: json.loads((ROOT / f"data/benchmark/splits/temporal_submit_{name}.json").read_text(encoding="utf-8"))
        for name in ("train", "val", "test")
    }
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    axes[0].bar(["Positive", "Negative"], [sum(r["label"] for r in dd), sum(1 - r["label"] for r in dd)], color=["#2878B5", "#9E9E9E"])
    axes[0].set_title("DD test composition")
    axes[0].set_ylabel("Candidate pairs")
    ranges = [(min(r["pair_date"] for r in part), max(r["pair_date"] for r in part)) for part in ss_parts.values()]
    axes[1].barh(["Train", "Validation", "Test"], [len(v) for v in ss_parts.values()], color=["#4E79A7", "#F28E2B", "#59A14F"])
    axes[1].set_title("SS partitions")
    axes[1].set_xlabel("Candidate pairs")
    for index, (start, end) in enumerate(ranges):
        axes[1].text(15, index, f"{start} – {end}", va="center", color="white", fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "figure2_benchmark_data.pdf", bbox_inches="tight")
    plt.close(fig)


def figure3(output: Path) -> None:
    main = rows(ROOT / "results/source_data/main_performance.csv")
    ablations = rows(ROOT / "results/source_data/ablation_performance.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    workflows = ["Direct", "CoT", "RAG+Tools", "TreatAgent"]
    x = range(len(workflows))
    width = 0.36
    for offset, split in ((-width / 2, "drug_disjoint"), (width / 2, "submission_date_separated")):
        subset = {r["workflow"]: r for r in main if r["split"] == split}
        axes[0].bar([i + offset for i in x], [float(subset[w]["f1"]) for w in workflows], width=width, label="DD" if split == "drug_disjoint" else "SS")
    axes[0].set_xticks(list(x), workflows, rotation=20, ha="right")
    axes[0].set_ylim(0, 0.8)
    axes[0].set_ylabel("F1")
    axes[0].set_title("Main comparison")
    axes[0].legend(frameon=False)
    selected = [r for r in ablations if r["split"] == "drug_disjoint"]
    axes[1].barh([r["workflow"] for r in selected], [float(r["f1"]) for r in selected], color="#4E79A7")
    axes[1].set_xlim(0.55, 0.78)
    axes[1].set_xlabel("F1")
    axes[1].set_title("DD ablations")
    fig.tight_layout()
    fig.savefig(output / "figure3_performance_data.pdf", bbox_inches="tight")
    plt.close(fig)


def figure4(output: Path) -> None:
    case_dir = ROOT / "results/case_studies"
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(case_dir.glob("*.json"))]
    records = [case["results"][0] for case in cases]
    labels = [f"{row['drug_names'][0] if row['drug_names'] else row['sample_id']}\n{row['disease']}" for row in records]
    scores = [float(row["prediction_score"]) for row in records]
    colors = ["#2878B5" if row["prediction_binary"] else "#9E9E9E" for row in records]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.bar(labels, scores, color=colors)
    ax.axhline(0.2, color="#C44E52", linestyle="--", linewidth=1, label="TreatAgent threshold")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Research-priority score")
    ax.set_title("Representative case-study scores")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output / "figure4_case_study_data.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reproduced_figures")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figure2(args.output_dir)
    figure3(args.output_dir)
    figure4(args.output_dir)
    print(f"Wrote data-level figure reproductions to {args.output_dir}")


if __name__ == "__main__":
    main()

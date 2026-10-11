import os
import sys
import json
import csv
import re
import argparse
from datetime import datetime
from collections import defaultdict
from rapidfuzz import fuzz

# Add root and src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from main import get_ollama_embedding
from db import DSM5Database

def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and replacing punctuation with spaces."""
    if not text:
        return ""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(text.split())

def enrich_chunk(chunk: dict) -> dict:
    """
    Standardize chunk page metadata:
    - pdf_page: 1-based PDF page index from PyMuPDF
    - printed_page: estimated DSM-5 book page (calibrated offset of 38 pages in Section II)
    """
    pdf_p = chunk.get("pdf_page") or chunk.get("page_number")
    chunk["pdf_page"] = pdf_p
    if chunk.get("printed_page") is None:
        chunk["printed_page"] = (pdf_p - 38) if (pdf_p and pdf_p > 38) else None
    return chunk

def is_disorder_hit(chunk: dict, gold_disorders: list) -> bool:
    """
    Check if retrieved chunk's disorder matches gold_disorders.
    Normalized case/punctuation, RapidFuzz score >= 90.0.
    Guards Roman numerals (e.g. Bipolar I vs Bipolar II) and residual categories.
    """
    c_dis = chunk.get("disorder_name", "")
    n_cd = normalize_text(c_dis)
    if not n_cd or not gold_disorders:
        return False

    for gd in gold_disorders:
        n_gd = normalize_text(gd)
        if not n_gd:
            continue

        # Guard Roman numerals (e.g. Bipolar I vs Bipolar II)
        r_gd = re.findall(r"\b(i|ii|iii|iv|v)\b", n_gd)
        r_cd = re.findall(r"\b(i|ii|iii|iv|v)\b", n_cd)
        if r_gd and r_cd and set(r_gd) != set(r_cd):
            continue

        # Guard residual categories ("other specified", "unspecified")
        is_gd_residual = any(w in n_gd for w in ["other specified", "unspecified"])
        is_cd_residual = any(w in n_cd for w in ["other specified", "unspecified"])
        if is_cd_residual != is_gd_residual:
            continue

        # RapidFuzz match
        score = max(
            fuzz.token_set_ratio(n_gd, n_cd),
            fuzz.token_sort_ratio(n_gd, n_cd),
            fuzz.ratio(n_gd, n_cd)
        )
        if score >= 90.0:
            return True

    return False

def is_section_match(chunk: dict, gold_sections: list) -> bool:
    """
    Exact case-insensitive match on section_type.
    If gold_sections is empty, defaults to True.
    """
    if not gold_sections:
        return True
    c_sec = (chunk.get("section_type") or "").strip().lower()
    return any(c_sec == gs.strip().lower() for gs in gold_sections)

def compute_auroc(in_scope_scores: list, oos_scores: list) -> float:
    """
    Compute AUROC of top-score separating in-scope vs out-of-scope
    using the Wilcoxon-Mann-Whitney U-statistic.
    """
    if not in_scope_scores or not oos_scores:
        return 0.0

    u_stat = 0.0
    for x in in_scope_scores:
        for y in oos_scores:
            if x > y:
                u_stat += 1.0
            elif x == y:
                u_stat += 0.5

    return u_stat / (len(in_scope_scores) * len(oos_scores))

def sweep_thresholds(in_scope_scores: list, oos_scores: list) -> dict:
    """
    Sweep thresholds from 0.50 to 0.90 to find the optimal cutoff for OOS rejection.
    Optimizes for Balanced Accuracy = (TPR + TNR) / 2.
    """
    if not in_scope_scores or not oos_scores:
        return {
            "optimal_threshold": 0.65,
            "balanced_accuracy": 0.0,
            "oos_rejection_acc": 0.0,
            "in_scope_retention": 0.0,
            "sweep_table": []
        }

    best_bal_acc = -1.0
    best_th = 0.65
    best_tpr = 0.0
    best_tnr = 0.0
    sweep_table = []

    candidates = [round(0.50 + i * 0.01, 2) for i in range(41)]

    for th in candidates:
        in_retained = sum(1 for s in in_scope_scores if s >= th)
        oos_rejected = sum(1 for s in oos_scores if s < th)
        tpr = in_retained / len(in_scope_scores)
        tnr = oos_rejected / len(oos_scores)
        bal_acc = (tpr + tnr) / 2.0

        sweep_table.append({
            "threshold": th,
            "in_scope_retention": tpr,
            "oos_rejection": tnr,
            "balanced_accuracy": bal_acc
        })

        if bal_acc > best_bal_acc:
            best_bal_acc = bal_acc
            best_th = th
            best_tpr = tpr
            best_tnr = tnr

    return {
        "optimal_threshold": best_th,
        "balanced_accuracy": best_bal_acc,
        "oos_rejection_acc": best_tnr,
        "in_scope_retention": best_tpr,
        "sweep_table": sweep_table
    }

def default_retrieve_fn(query: str, k: int = 10, db: DSM5Database = None):
    """Retrieve top-k chunks using baseline bge-large + Pinecone/SQLite."""
    query_vector = get_ollama_embedding(query)
    matches = db.search(query_vector, k=k)
    return matches

def calculate_split_metrics(q_results: list, oos_threshold: float):
    """Calculate primary, secondary, and per-type metrics for a given subset of questions."""
    in_scope = [q for q in q_results if q["type"] != "out_of_scope"]
    oos = [q for q in q_results if q["type"] == "out_of_scope"]

    in_top_scores = [q["top_score"] for q in in_scope]
    oos_top_scores = [q["top_score"] for q in oos]

    auroc = compute_auroc(in_top_scores, oos_top_scores)

    # Primary metric: disorder match AND exact section_type
    primary_h5 = [q["primary_hit_5"] for q in in_scope]
    primary_h10 = [q["primary_hit_10"] for q in in_scope]
    primary_rr = [q["primary_rr"] for q in in_scope]

    # Secondary metric: disorder match only
    disorder_h5 = [q["disorder_hit_5"] for q in in_scope]
    disorder_h10 = [q["disorder_hit_10"] for q in in_scope]
    disorder_rr = [q["disorder_rr"] for q in in_scope]

    mean_primary_h5 = sum(primary_h5) / len(primary_h5) if primary_h5 else 0.0
    mean_primary_h10 = sum(primary_h10) / len(primary_h10) if primary_h10 else 0.0
    mean_primary_mrr = sum(primary_rr) / len(primary_rr) if primary_rr else 0.0

    mean_disorder_h5 = sum(disorder_h5) / len(disorder_h5) if disorder_h5 else 0.0
    mean_disorder_h10 = sum(disorder_h10) / len(disorder_h10) if disorder_h10 else 0.0
    mean_disorder_mrr = sum(disorder_rr) / len(disorder_rr) if disorder_rr else 0.0

    # Per question type breakdown
    type_breakdown = {}
    grouped_by_type = defaultdict(list)
    for q in in_scope:
        grouped_by_type[q["type"]].append(q)

    for qtype, items in grouped_by_type.items():
        type_breakdown[qtype] = {
            "count": len(items),
            "primary_hit_5": sum(x["primary_hit_5"] for x in items) / len(items),
            "primary_hit_10": sum(x["primary_hit_10"] for x in items) / len(items),
            "primary_mrr": sum(x["primary_rr"] for x in items) / len(items),
            "disorder_hit_5": sum(x["disorder_hit_5"] for x in items) / len(items),
            "disorder_hit_10": sum(x["disorder_hit_10"] for x in items) / len(items),
            "disorder_mrr": sum(x["disorder_rr"] for x in items) / len(items),
        }

    # OOS performance
    oos_rejected = sum(1 for s in oos_top_scores if s < oos_threshold)
    oos_acc = oos_rejected / len(oos_top_scores) if oos_top_scores else 0.0

    in_retained = sum(1 for s in in_top_scores if s >= oos_threshold)
    in_retention = in_retained / len(in_top_scores) if in_top_scores else 0.0
    bal_acc = (in_retention + oos_acc) / 2.0

    return {
        "count_in_scope": len(in_scope),
        "count_oos": len(oos),
        "primary_hit_5": round(mean_primary_h5, 4),
        "primary_hit_10": round(mean_primary_h10, 4),
        "primary_mrr": round(mean_primary_mrr, 4),
        "disorder_hit_5": round(mean_disorder_h5, 4),
        "disorder_hit_10": round(mean_disorder_h10, 4),
        "disorder_mrr": round(mean_disorder_mrr, 4),
        "by_type": type_breakdown,
        "auroc": round(auroc, 4),
        "oos_threshold": round(oos_threshold, 2),
        "oos_rejection_acc": round(oos_acc, 4),
        "in_scope_retention": round(in_retention, 4),
        "balanced_accuracy": round(bal_acc, 4)
    }

def run_evaluation(retrieve_fn=None, config_label="v0-legacy", questions_path=None, results_csv="results.csv"):
    if questions_path is None:
        questions_path = os.path.join(PROJECT_ROOT, "eval", "questions.jsonl")

    # Load questions
    questions = []
    with open(questions_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    # Initialize DB connection
    db = DSM5Database()

    print(f"\n=======================================================")
    print(f"RUNNING EVALUATION: {config_label}")
    print(f"Total Questions: {len(questions)} (Dev/Test Stratified)")
    print(f"=======================================================\n")

    per_question_results = []

    for idx, q in enumerate(questions, 1):
        qid = q["id"]
        qtype = q["type"]
        qsplit = q.get("split", "test")
        qtext = q["question"]
        g_disorders = q.get("gold_disorders", [])
        g_sections = q.get("gold_sections", [])
        g_pages = q.get("gold_pages", [])

        # Retrieve top 10
        if retrieve_fn is None:
            retrieved = default_retrieve_fn(qtext, k=10, db=db)
        else:
            retrieved = retrieve_fn(qtext, k=10)

        # Standardize page metadata
        for chunk in retrieved:
            enrich_chunk(chunk)

        top_score = retrieved[0]["score"] if retrieved else 0.0

        raw_chunks_info = []
        disorder_hit_ranks = []
        primary_hit_ranks = []

        for rank, chunk in enumerate(retrieved, start=1):
            d_hit = is_disorder_hit(chunk, g_disorders) if qtype != "out_of_scope" else False
            sec_match = is_section_match(chunk, g_sections) if qtype != "out_of_scope" else False
            prim_hit = (d_hit and sec_match) if qtype != "out_of_scope" else False

            if d_hit:
                disorder_hit_ranks.append(rank)
            if prim_hit:
                primary_hit_ranks.append(rank)

            raw_chunks_info.append({
                "rank": rank,
                "disorder_name": chunk.get("disorder_name"),
                "section_type": chunk.get("section_type"),
                "pdf_page": chunk.get("pdf_page"),
                "printed_page": chunk.get("printed_page"),
                "score": round(float(chunk.get("score", 0.0)), 4),
                "disorder_hit": d_hit,
                "section_match": sec_match,
                "primary_hit": prim_hit
            })

        prim_h5 = 1.0 if any(r <= 5 for r in primary_hit_ranks) else 0.0
        prim_h10 = 1.0 if any(r <= 10 for r in primary_hit_ranks) else 0.0
        prim_rr = (1.0 / primary_hit_ranks[0]) if primary_hit_ranks else 0.0

        dis_h5 = 1.0 if any(r <= 5 for r in disorder_hit_ranks) else 0.0
        dis_h10 = 1.0 if any(r <= 10 for r in disorder_hit_ranks) else 0.0
        dis_rr = (1.0 / disorder_hit_ranks[0]) if disorder_hit_ranks else 0.0

        top_matches_desc = [
            f"#{r['rank']}: {r['disorder_name']} ({r['section_type']}, pdf_p.{r['pdf_page']}, s={r['score']:.3f})"
            for r in raw_chunks_info[:3]
        ]

        per_question_results.append({
            "id": qid,
            "type": qtype,
            "split": qsplit,
            "question": qtext,
            "gold_disorders": g_disorders,
            "gold_sections": g_sections,
            "gold_pages": g_pages,
            "top_score": top_score,
            "primary_hit_5": prim_h5,
            "primary_hit_10": prim_h10,
            "primary_rr": prim_rr,
            "disorder_hit_5": dis_h5,
            "disorder_hit_10": dis_h10,
            "disorder_rr": dis_rr,
            "primary_hit_ranks": primary_hit_ranks,
            "disorder_hit_ranks": disorder_hit_ranks,
            "details": f"Primary Hits: {primary_hit_ranks} | Disorder Hits: {disorder_hit_ranks} | Top: {' | '.join(top_matches_desc)}",
            "retrieved": raw_chunks_info
        })

    # Separate Dev and Test splits
    dev_results = [q for q in per_question_results if q["split"] == "dev"]
    test_results = [q for q in per_question_results if q["split"] == "test"]

    # 1. TUNE OOS THRESHOLD ON DEV ONLY
    dev_in_scope_scores = [q["top_score"] for q in dev_results if q["type"] != "out_of_scope"]
    dev_oos_scores = [q["top_score"] for q in dev_results if q["type"] == "out_of_scope"]

    dev_sweep = sweep_thresholds(dev_in_scope_scores, dev_oos_scores)
    optimal_dev_threshold = dev_sweep["optimal_threshold"]

    # 2. EVALUATE ON TEST (AND DEV) USING OPTIMAL DEV THRESHOLD
    dev_metrics = calculate_split_metrics(dev_results, optimal_dev_threshold)
    test_metrics = calculate_split_metrics(test_results, optimal_dev_threshold)

    # Mark success booleans based on optimal dev threshold
    for q in per_question_results:
        if q["type"] == "out_of_scope":
            q["success"] = q["top_score"] < optimal_dev_threshold
            q["details"] = f"Top Score: {q['top_score']:.4f} (Cutoff: {optimal_dev_threshold:.2f})"
        else:
            q["success"] = q["primary_hit_5"] > 0

    print("=========================================================================================")
    print(f"HEADLINE EVALUATION RESULTS: {config_label} (TEST SET, N={len(test_results)})")
    print(f"Threshold tuned on DEV: {optimal_dev_threshold:.2f} (Dev Balanced Acc: {dev_metrics['balanced_accuracy']:.2%})")
    print("=========================================================================================")
    print(f"PRIMARY METRIC (Disorder AND Exact Section Type):")
    print(f"  Hit@5  : {test_metrics['primary_hit_5']:.4f}")
    print(f"  Hit@10 : {test_metrics['primary_hit_10']:.4f}")
    print(f"  MRR    : {test_metrics['primary_mrr']:.4f}")
    print("-----------------------------------------------------------------------------------------")
    print(f"SECONDARY METRIC (Disorder-Only Fuzzy >= 90):")
    print(f"  Hit@5  : {test_metrics['disorder_hit_5']:.4f}")
    print(f"  Hit@10 : {test_metrics['disorder_hit_10']:.4f}")
    print(f"  MRR    : {test_metrics['disorder_mrr']:.4f}")
    print("-----------------------------------------------------------------------------------------")
    print(f"OUT-OF-SCOPE REJECTION (Test Cutoff @ {optimal_dev_threshold:.2f}):")
    print(f"  AUROC (In-Scope vs OOS) : {test_metrics['auroc']:.4f}")
    print(f"  OOS Rejection Accuracy  : {test_metrics['oos_rejection_acc']:.4f} ({int(test_metrics['oos_rejection_acc'] * test_metrics['count_oos'])}/{test_metrics['count_oos']})")
    print(f"  In-Scope Retained       : {test_metrics['in_scope_retention']:.4f} ({int(test_metrics['in_scope_retention'] * test_metrics['count_in_scope'])}/{test_metrics['count_in_scope']})")
    print(f"  Balanced Accuracy       : {test_metrics['balanced_accuracy']:.4f}")
    print("-----------------------------------------------------------------------------------------")
    print("TEST BREAKDOWN BY QUESTION TYPE:")
    print(f"{'Type':16s} | {'Count':5s} | {'Primary Hit@5':14s} | {'Primary MRR':11s} | {'Disorder Hit@5':15s} | {'Disorder MRR':12s}")
    print("-" * 88)
    for qtype in ["lookup", "differential", "vignette", "detail_lookup"]:
        if qtype in test_metrics["by_type"]:
            tm = test_metrics["by_type"][qtype]
            print(f"{qtype:16s} | {tm['count']:5d} | {tm['primary_hit_5']:14.4f} | {tm['primary_mrr']:11.4f} | {tm['disorder_hit_5']:15.4f} | {tm['disorder_mrr']:12.4f}")
    print("=========================================================================================\n")

    print("------------------- DEV SET COMPARISON -------------------")
    print(f"Primary Hit@5 : {dev_metrics['primary_hit_5']:.4f} | Primary MRR : {dev_metrics['primary_mrr']:.4f}")
    print(f"Disorder Hit@5: {dev_metrics['disorder_hit_5']:.4f} | Disorder MRR: {dev_metrics['disorder_mrr']:.4f}")
    print(f"OOS Rejection : {dev_metrics['oos_rejection_acc']:.4f} | Dev AUROC   : {dev_metrics['auroc']:.4f}")
    print("----------------------------------------------------------\n")

    # Show failures on test set
    test_failures = [q for q in test_results if not q["success"]]
    print(f"---------------- TEST FAILURES (Primary Hit@5 / OOS Rejection: {len(test_failures)}) ----------------")
    if not test_failures:
        print("None! All test questions succeeded.")
    else:
        for f in test_failures:
            print(f"[{f['id']}] ({f['type'].upper()}) {f['question']}")
            print(f"   Reason: {f['details']}")
    print("--------------------------------------------------------------------------------------\n")

    # Save raw rankings to eval/runs/<label>.json
    runs_dir = os.path.join(PROJECT_ROOT, "eval", "runs")
    os.makedirs(runs_dir, exist_ok=True)
    run_file_path = os.path.join(runs_dir, f"{config_label}.json")

    run_payload = {
        "label": config_label,
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(questions),
        "dev_tuning": {
            "optimal_threshold": optimal_dev_threshold,
            "dev_balanced_accuracy": dev_sweep["balanced_accuracy"],
            "dev_sweep": [s for s in dev_sweep["sweep_table"] if s["threshold"] in [0.55, 0.60, 0.65, 0.68, 0.70, 0.71, 0.72, 0.75, 0.80]]
        },
        "test_metrics": test_metrics,
        "dev_metrics": dev_metrics,
        "questions": per_question_results
    }

    with open(run_file_path, "w", encoding="utf-8") as rf:
        json.dump(run_payload, rf, indent=2)
    print(f"Raw rankings and run artifact saved to: {run_file_path}")

    # Append headline test numbers to results.csv
    csv_file_path = os.path.join(PROJECT_ROOT, results_csv)
    file_exists = os.path.exists(csv_file_path)

    fieldnames = [
        "timestamp", "config_label", "split", "total_questions",
        "primary_hit@5", "primary_hit@10", "primary_mrr",
        "disorder_hit@5", "disorder_hit@10", "disorder_mrr",
        "lookup_hit@5", "lookup_mrr",
        "diff_hit@5", "diff_mrr",
        "vignette_hit@5", "vignette_mrr",
        "detail_hit@5", "detail_mrr",
        "oos_rejection_acc", "dev_optimal_threshold", "test_auroc"
    ]

    with open(csv_file_path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        lookup_stats = test_metrics["by_type"].get("lookup", {})
        diff_stats = test_metrics["by_type"].get("differential", {})
        vig_stats = test_metrics["by_type"].get("vignette", {})
        det_stats = test_metrics["by_type"].get("detail_lookup", {})

        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "config_label": config_label,
            "split": "test",
            "total_questions": len(test_results),
            "primary_hit@5": test_metrics["primary_hit_5"],
            "primary_hit@10": test_metrics["primary_hit_10"],
            "primary_mrr": test_metrics["primary_mrr"],
            "disorder_hit@5": test_metrics["disorder_hit_5"],
            "disorder_hit@10": test_metrics["disorder_hit_10"],
            "disorder_mrr": test_metrics["disorder_mrr"],
            "lookup_hit@5": lookup_stats.get("primary_hit_5", 0.0),
            "lookup_mrr": lookup_stats.get("primary_mrr", 0.0),
            "diff_hit@5": diff_stats.get("primary_hit_5", 0.0),
            "diff_mrr": diff_stats.get("primary_mrr", 0.0),
            "vignette_hit@5": vig_stats.get("primary_hit_5", 0.0),
            "vignette_mrr": vig_stats.get("primary_mrr", 0.0),
            "detail_hit@5": det_stats.get("primary_hit_5", 0.0),
            "detail_mrr": det_stats.get("primary_mrr", 0.0),
            "oos_rejection_acc": test_metrics["oos_rejection_acc"],
            "dev_optimal_threshold": optimal_dev_threshold,
            "test_auroc": test_metrics["auroc"]
        })

    print(f"Headline test results appended to {results_csv}")
    db.close()
    return per_question_results, run_payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSM-5 Retrieval Evaluation Runner")
    parser.add_argument("--config", "--label", dest="config_label", default="v0-legacy", help="Configuration label for run")
    parser.add_argument("--questions", dest="questions_path", default=None, help="Path to questions.jsonl")
    parser.add_argument("--csv", dest="results_csv", default="results.csv", help="Results CSV output path")
    args = parser.parse_args()

    run_evaluation(config_label=args.config_label, questions_path=args.questions_path, results_csv=args.results_csv)

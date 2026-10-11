import os
import sys
import json
import csv
import re
import argparse
from datetime import datetime
from rapidfuzz import fuzz

# Add root and src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from main import get_ollama_embedding
from db import DSM5Database

def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and stripping punctuation to spaces."""
    if not text:
        return ""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(text.split())

def enrich_chunk(chunk: dict) -> dict:
    """
    Standardize chunk page metadata:
    - pdf_page: 1-based PDF document page
    - printed_page: estimated DSM-5 printed book page (offset 38 in Section II)
    """
    pdf_p = chunk.get("pdf_page") or chunk.get("page_number")
    chunk["pdf_page"] = pdf_p
    if chunk.get("printed_page") is None:
        chunk["printed_page"] = (pdf_p - 38) if (pdf_p and pdf_p > 38) else None
    return chunk

def is_disorder_hit(chunk: dict, gold_disorders: list) -> bool:
    """
    Hit criterion: retrieved chunk's disorder matches gold_disorders
    (normalize case/punctuation, fuzzy score >= 90 via rapidfuzz).
    Page is diagnostic only; chunk ID is never used.
    """
    c_dis = chunk.get("disorder_name", "")
    n_cd = normalize_text(c_dis)
    if not n_cd or not gold_disorders:
        return False

    for gd in gold_disorders:
        n_gd = normalize_text(gd)
        if not n_gd:
            continue

        # Guard Roman numerals (e.g., Bipolar I vs Bipolar II)
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

def is_section_hit(chunk: dict, gold_sections: list) -> bool:
    """
    Optional section match check (reported separately).
    """
    if not gold_sections:
        return True
    c_sec = chunk.get("section_type", "")
    n_cs = normalize_text(c_sec)
    if not n_cs:
        return False

    for gs in gold_sections:
        n_gs = normalize_text(gs)
        if not n_gs:
            continue
        if n_gs in n_cs or n_cs in n_gs:
            return True
        score = fuzz.token_set_ratio(n_gs, n_cs)
        if score >= 90.0:
            return True
    return False

def compute_auroc(in_scope_scores: list, oos_scores: list) -> float:
    """
    Compute AUROC of top-score separating in-scope vs out-of-scope
    using the exact Wilcoxon-Mann-Whitney U-statistic.
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

    # Check candidates from 0.50 to 0.90 in increments of 0.01
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

    recalls_at_5 = []
    recalls_at_10 = []
    rr_list = []

    sec_recalls_at_5 = []
    sec_recalls_at_10 = []

    type_metrics = {
        "lookup": {"hits_at_5": 0, "hits_at_10": 0, "rr": [], "total": 0},
        "differential": {"hits_at_5": 0, "hits_at_10": 0, "rr": [], "total": 0},
        "out_of_scope": {"total": 0, "top_scores": []}
    }

    per_question_results = []
    raw_rankings = []
    in_scope_top_scores = []
    oos_top_scores = []

    print(f"\n=======================================================")
    print(f"RUNNING EVALUATION: {config_label}")
    print(f"Total Questions: {len(questions)}")
    print(f"=======================================================\n")

    for idx, q in enumerate(questions):
        qid = q["id"]
        qtype = q["type"]
        qtext = q["question"]
        g_disorders = q.get("gold_disorders", [])
        g_pages = q.get("gold_pages", [])
        g_sections = q.get("gold_sections", [])

        # Retrieve top 10
        if retrieve_fn is None:
            retrieved = default_retrieve_fn(qtext, k=10, db=db)
        else:
            retrieved = retrieve_fn(qtext, k=10)

        # Enrich chunk metadata with pdf_page and printed_page
        for chunk in retrieved:
            enrich_chunk(chunk)

        top_score = retrieved[0]["score"] if retrieved else 0.0

        # Build raw ranking record for this question
        raw_chunks_info = []
        disorder_hit_ranks = []
        section_hit_ranks = []

        for rank, chunk in enumerate(retrieved, start=1):
            d_hit = is_disorder_hit(chunk, g_disorders) if qtype != "out_of_scope" else False
            s_hit = (d_hit and is_section_hit(chunk, g_sections)) if qtype != "out_of_scope" else False

            if d_hit:
                disorder_hit_ranks.append(rank)
            if s_hit:
                section_hit_ranks.append(rank)

            raw_chunks_info.append({
                "rank": rank,
                "disorder_name": chunk.get("disorder_name"),
                "section_type": chunk.get("section_type"),
                "pdf_page": chunk.get("pdf_page"),
                "printed_page": chunk.get("printed_page"),
                "score": round(float(chunk.get("score", 0.0)), 4),
                "is_disorder_hit": d_hit,
                "is_section_hit": s_hit
            })

        if qtype == "out_of_scope":
            oos_top_scores.append(top_score)
            type_metrics["out_of_scope"]["total"] += 1
            type_metrics["out_of_scope"]["top_scores"].append(top_score)

            per_question_results.append({
                "id": qid,
                "type": qtype,
                "question": qtext,
                "top_score": top_score,
                "retrieved": raw_chunks_info
            })
        else:
            in_scope_top_scores.append(top_score)

            hit_5 = 1.0 if any(r <= 5 for r in disorder_hit_ranks) else 0.0
            hit_10 = 1.0 if any(r <= 10 for r in disorder_hit_ranks) else 0.0
            first_rr = (1.0 / disorder_hit_ranks[0]) if disorder_hit_ranks else 0.0

            sec_hit_5 = 1.0 if any(r <= 5 for r in section_hit_ranks) else 0.0
            sec_hit_10 = 1.0 if any(r <= 10 for r in section_hit_ranks) else 0.0

            recalls_at_5.append(hit_5)
            recalls_at_10.append(hit_10)
            rr_list.append(first_rr)

            sec_recalls_at_5.append(sec_hit_5)
            sec_recalls_at_10.append(sec_hit_10)

            type_metrics[qtype]["total"] += 1
            type_metrics[qtype]["hits_at_5"] += hit_5
            type_metrics[qtype]["hits_at_10"] += hit_10
            type_metrics[qtype]["rr"].append(first_rr)

            top_matches_desc = [
                f"#{r['rank']}: {r['disorder_name']} ({r['section_type']}, pdf_p.{r['pdf_page']}, score={r['score']:.3f})"
                for r in raw_chunks_info[:3]
            ]

            per_question_results.append({
                "id": qid,
                "type": qtype,
                "question": qtext,
                "gold_disorders": g_disorders,
                "gold_sections": g_sections,
                "gold_pages": g_pages,
                "success": hit_5 > 0,
                "disorder_hit_ranks": disorder_hit_ranks,
                "section_hit_ranks": section_hit_ranks,
                "first_hit_rank": disorder_hit_ranks[0] if disorder_hit_ranks else None,
                "top_score": top_score,
                "details": f"Disorder Hits: {disorder_hit_ranks} | Section Hits: {section_hit_ranks} | Top: {' | '.join(top_matches_desc)}",
                "retrieved": raw_chunks_info
            })

    # Summary calculations for in-scope
    mean_recall_5 = sum(recalls_at_5) / len(recalls_at_5) if recalls_at_5 else 0.0
    mean_recall_10 = sum(recalls_at_10) / len(recalls_at_10) if recalls_at_10 else 0.0
    mean_mrr = sum(rr_list) / len(rr_list) if rr_list else 0.0

    mean_sec_r5 = sum(sec_recalls_at_5) / len(sec_recalls_at_5) if sec_recalls_at_5 else 0.0
    mean_sec_r10 = sum(sec_recalls_at_10) / len(sec_recalls_at_10) if sec_recalls_at_10 else 0.0

    lookup_r5 = type_metrics["lookup"]["hits_at_5"] / type_metrics["lookup"]["total"] if type_metrics["lookup"]["total"] else 0.0
    lookup_r10 = type_metrics["lookup"]["hits_at_10"] / type_metrics["lookup"]["total"] if type_metrics["lookup"]["total"] else 0.0
    lookup_mrr = sum(type_metrics["lookup"]["rr"]) / type_metrics["lookup"]["total"] if type_metrics["lookup"]["total"] else 0.0

    diff_r5 = type_metrics["differential"]["hits_at_5"] / type_metrics["differential"]["total"] if type_metrics["differential"]["total"] else 0.0
    diff_r10 = type_metrics["differential"]["hits_at_10"] / type_metrics["differential"]["total"] if type_metrics["differential"]["total"] else 0.0
    diff_mrr = sum(type_metrics["differential"]["rr"]) / type_metrics["differential"]["total"] if type_metrics["differential"]["total"] else 0.0

    # AUROC & Threshold Sweep for Out-of-Scope
    oos_auroc = compute_auroc(in_scope_top_scores, oos_top_scores)
    sweep_results = sweep_thresholds(in_scope_top_scores, oos_top_scores)
    optimal_th = sweep_results["optimal_threshold"]
    oos_rejection_acc = sweep_results["oos_rejection_acc"]
    in_scope_retention = sweep_results["in_scope_retention"]
    balanced_acc = sweep_results["balanced_accuracy"]

    # Mark out_of_scope success based on optimal threshold
    for res in per_question_results:
        if res["type"] == "out_of_scope":
            res["success"] = res["top_score"] < optimal_th
            res["details"] = f"Top score: {res['top_score']:.4f} (Optimal Threshold: {optimal_th:.2f})"

    print("-------------------- RESULTS SUMMARY --------------------")
    print(f"Overall In-Scope Recall@5 : {mean_recall_5:.4f}")
    print(f"Overall In-Scope Recall@10: {mean_recall_10:.4f}")
    print(f"Overall In-Scope MRR      : {mean_mrr:.4f}")
    print(f"Section Match Recall@5    : {mean_sec_r5:.4f}")
    print(f"Section Match Recall@10   : {mean_sec_r10:.4f}")
    print("---------------------------------------------------------")
    print(f"Lookup       -> Recall@5: {lookup_r5:.4f} | Recall@10: {lookup_r10:.4f} | MRR: {lookup_mrr:.4f}")
    print(f"Differential -> Recall@5: {diff_r5:.4f} | Recall@10: {diff_r10:.4f} | MRR: {diff_mrr:.4f}")
    print("----------------- OUT-OF-SCOPE METRICS ------------------")
    print(f"AUROC (In-Scope vs OOS)   : {oos_auroc:.4f}")
    print(f"Optimal OOS Cutoff        : {optimal_th:.2f}")
    print(f"OOS Rejection Acc @ {optimal_th:.2f} : {oos_rejection_acc:.4f} ({int(oos_rejection_acc * len(oos_top_scores))}/{len(oos_top_scores)})")
    print(f"In-Scope Retained @ {optimal_th:.2f} : {in_scope_retention:.4f} ({int(in_scope_retention * len(in_scope_top_scores))}/{len(in_scope_top_scores)})")
    print(f"Balanced Accuracy         : {balanced_acc:.4f}")
    print("---------------------------------------------------------\n")

    # Show failures
    print("----------------- PER-QUESTION FAILURES -----------------")
    failures = [r for r in per_question_results if not r["success"]]
    if not failures:
        print("None! All questions passed Recall@5 / OOS Rejection.")
    else:
        for f in failures:
            print(f"[{f['id']}] ({f['type'].upper()}) {f['question']}")
            print(f"   Reason: {f['details']}")
    print("---------------------------------------------------------\n")

    # Save per-run raw rankings to eval/runs/<label>.json
    runs_dir = os.path.join(PROJECT_ROOT, "eval", "runs")
    os.makedirs(runs_dir, exist_ok=True)
    run_file_path = os.path.join(runs_dir, f"{config_label}.json")

    run_payload = {
        "label": config_label,
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(questions),
        "metrics": {
            "recall_at_5": round(mean_recall_5, 4),
            "recall_at_10": round(mean_recall_10, 4),
            "mrr": round(mean_mrr, 4),
            "section_recall_at_5": round(mean_sec_r5, 4),
            "section_recall_at_10": round(mean_sec_r10, 4),
            "lookup_recall_at_5": round(lookup_r5, 4),
            "lookup_recall_at_10": round(lookup_r10, 4),
            "lookup_mrr": round(lookup_mrr, 4),
            "diff_recall_at_5": round(diff_r5, 4),
            "diff_recall_at_10": round(diff_r10, 4),
            "diff_mrr": round(diff_mrr, 4),
            "oos_auroc": round(oos_auroc, 4),
            "optimal_oos_threshold": round(optimal_th, 2),
            "oos_rejection_acc": round(oos_rejection_acc, 4),
            "balanced_accuracy": round(balanced_acc, 4)
        },
        "threshold_sweep": [
            s for s in sweep_results["sweep_table"]
            if s["threshold"] in [0.55, 0.60, 0.65, 0.68, 0.70, 0.71, 0.72, 0.75, 0.80]
        ],
        "questions": per_question_results
    }

    with open(run_file_path, "w", encoding="utf-8") as rf:
        json.dump(run_payload, rf, indent=2)
    print(f"Raw rankings and run artifact saved to: {run_file_path}")

    # Append to results.csv
    csv_file_path = os.path.join(PROJECT_ROOT, results_csv)
    file_exists = os.path.exists(csv_file_path)

    with open(csv_file_path, "a", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp", "config_label", "total_questions",
            "recall@5", "recall@10", "mrr",
            "section_recall@5", "section_recall@10",
            "lookup_recall@5", "lookup_mrr",
            "diff_recall@5", "diff_mrr",
            "oos_auroc", "optimal_oos_threshold", "oos_rejection_acc"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "config_label": config_label,
            "total_questions": len(questions),
            "recall@5": round(mean_recall_5, 4),
            "recall@10": round(mean_recall_10, 4),
            "mrr": round(mean_mrr, 4),
            "section_recall@5": round(mean_sec_r5, 4),
            "section_recall@10": round(mean_sec_r10, 4),
            "lookup_recall@5": round(lookup_r5, 4),
            "lookup_mrr": round(lookup_mrr, 4),
            "diff_recall@5": round(diff_r5, 4),
            "diff_mrr": round(diff_mrr, 4),
            "oos_auroc": round(oos_auroc, 4),
            "optimal_oos_threshold": round(optimal_th, 2),
            "oos_rejection_acc": round(oos_rejection_acc, 4)
        })

    print(f"Results appended to {results_csv}")
    db.close()
    return per_question_results, run_payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSM-5 Retrieval Evaluation Runner")
    parser.add_argument("--config", "--label", dest="config_label", default="v0-legacy", help="Configuration label for run")
    parser.add_argument("--questions", dest="questions_path", default=None, help="Path to questions.jsonl")
    parser.add_argument("--csv", dest="results_csv", default="results.csv", help="Results CSV output path")
    args = parser.parse_args()

    run_evaluation(config_label=args.config_label, questions_path=args.questions_path, results_csv=args.results_csv)

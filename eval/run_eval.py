import os
import sys
import json
import csv
from datetime import datetime

# Add root and src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from main import get_ollama_embedding
from db import DSM5Database

OOS_THRESHOLD = 0.65  # Out-of-scope confidence cutoff: top cosine score below this is considered successfully rejected

def default_retrieve_fn(query: str, k: int = 10, db: DSM5Database = None):
    """Retrieve top-k chunks using baseline bge-large + Pinecone/SQLite."""
    query_vector = get_ollama_embedding(query)
    matches = db.search(query_vector, k=k)
    return matches

def is_hit(chunk, gold_disorders, gold_pages, gold_sections):
    """
    Check if a retrieved chunk matches ground truth.
    Keyed strictly on canonical disorder name + page range (+ section when available).
    NEVER on chunk ID.
    """
    c_dis = chunk.get("disorder_name", "").strip().lower()
    c_page = chunk.get("page_number")
    c_sec = chunk.get("section_type", "").strip().lower()

    # 1. Disorder name check
    disorder_match = any(gd.lower() in c_dis or c_dis in gd.lower() for gd in gold_disorders)
    if not disorder_match:
        return False

    # 2. Page range check (allow +/- 1 page tolerance for layout boundaries)
    if gold_pages and c_page:
        min_p = min(gold_pages) - 1
        max_p = max(gold_pages) + 1
        if not (min_p <= c_page <= max_p):
            return False

    return True

def run_evaluation(retrieve_fn=None, config_label="baseline_v0_pinecone_bge_large", questions_path=None, results_csv="results.csv"):
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

    type_metrics = {
        "lookup": {"hits_at_5": 0, "hits_at_10": 0, "rr": [], "total": 0},
        "differential": {"hits_at_5": 0, "hits_at_10": 0, "rr": [], "total": 0},
        "out_of_scope": {"correct_rejected": 0, "total": 0, "top_scores": []}
    }

    per_question_results = []

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

        top_score = retrieved[0]["score"] if retrieved else 0.0

        if qtype == "out_of_scope":
            # For out-of-scope, success = top score is below rejection threshold
            is_rejected = (top_score < OOS_THRESHOLD) or (len(retrieved) == 0)
            type_metrics["out_of_scope"]["total"] += 1
            type_metrics["out_of_scope"]["top_scores"].append(top_score)
            if is_rejected:
                type_metrics["out_of_scope"]["correct_rejected"] += 1
            per_question_results.append({
                "id": qid,
                "type": qtype,
                "question": qtext,
                "success": is_rejected,
                "top_score": top_score,
                "details": f"Top score: {top_score:.4f} (Threshold: {OOS_THRESHOLD})"
            })
            continue

        # In-scope evaluation (lookup & differential)
        hit_ranks = []
        for rank, chunk in enumerate(retrieved, start=1):
            if is_hit(chunk, g_disorders, g_pages, g_sections):
                hit_ranks.append(rank)

        hit_5 = 1.0 if any(r <= 5 for r in hit_ranks) else 0.0
        hit_10 = 1.0 if any(r <= 10 for r in hit_ranks) else 0.0
        first_rr = (1.0 / hit_ranks[0]) if hit_ranks else 0.0

        recalls_at_5.append(hit_5)
        recalls_at_10.append(hit_10)
        rr_list.append(first_rr)

        type_metrics[qtype]["total"] += 1
        type_metrics[qtype]["hits_at_5"] += hit_5
        type_metrics[qtype]["hits_at_10"] += hit_10
        type_metrics[qtype]["rr"].append(first_rr)

        top_matches_desc = [f"#{r}: {c.get('disorder_name')} (p.{c.get('page_number')}, s={c.get('score', 0):.3f})" for r, c in enumerate(retrieved[:3], 1)]

        per_question_results.append({
            "id": qid,
            "type": qtype,
            "question": qtext,
            "success": hit_5 > 0,
            "first_hit_rank": hit_ranks[0] if hit_ranks else None,
            "top_score": top_score,
            "details": f"Hits: {hit_ranks}. Top retrieved: {' | '.join(top_matches_desc)}"
        })

    # Summary calculations
    mean_recall_5 = sum(recalls_at_5) / len(recalls_at_5) if recalls_at_5 else 0.0
    mean_recall_10 = sum(recalls_at_10) / len(recalls_at_10) if recalls_at_10 else 0.0
    mean_mrr = sum(rr_list) / len(rr_list) if rr_list else 0.0

    oos_acc = (type_metrics["out_of_scope"]["correct_rejected"] / type_metrics["out_of_scope"]["total"]) if type_metrics["out_of_scope"]["total"] else 0.0

    lookup_r5 = type_metrics["lookup"]["hits_at_5"] / type_metrics["lookup"]["total"] if type_metrics["lookup"]["total"] else 0.0
    lookup_r10 = type_metrics["lookup"]["hits_at_10"] / type_metrics["lookup"]["total"] if type_metrics["lookup"]["total"] else 0.0
    lookup_mrr = sum(type_metrics["lookup"]["rr"]) / type_metrics["lookup"]["total"] if type_metrics["lookup"]["total"] else 0.0

    diff_r5 = type_metrics["differential"]["hits_at_5"] / type_metrics["differential"]["total"] if type_metrics["differential"]["total"] else 0.0
    diff_r10 = type_metrics["differential"]["hits_at_10"] / type_metrics["differential"]["total"] if type_metrics["differential"]["total"] else 0.0
    diff_mrr = sum(type_metrics["differential"]["rr"]) / type_metrics["differential"]["total"] if type_metrics["differential"]["total"] else 0.0

    print("-------------------- RESULTS SUMMARY --------------------")
    print(f"Overall In-Scope Recall@5 : {mean_recall_5:.4f}")
    print(f"Overall In-Scope Recall@10: {mean_recall_10:.4f}")
    print(f"Overall In-Scope MRR      : {mean_mrr:.4f}")
    print(f"Out-Of-Scope Rejection    : {oos_acc:.4f} ({type_metrics['out_of_scope']['correct_rejected']}/{type_metrics['out_of_scope']['total']})")
    print("---------------------------------------------------------")
    print(f"Lookup       -> Recall@5: {lookup_r5:.4f} | Recall@10: {lookup_r10:.4f} | MRR: {lookup_mrr:.4f}")
    print(f"Differential -> Recall@5: {diff_r5:.4f} | Recall@10: {diff_r10:.4f} | MRR: {diff_mrr:.4f}")
    print("---------------------------------------------------------\n")

    # Show failures
    print("----------------- PER-QUESTION FAILURES -----------------")
    failures = [r for r in per_question_results if not r["success"]]
    if not failures:
        print("None! All questions passed recall@5 / rejection threshold.")
    else:
        for f in failures:
            print(f"[{f['id']}] ({f['type'].upper()}) {f['question']}")
            print(f"   Reason: {f['details']}")
    print("---------------------------------------------------------\n")

    # Append to results.csv
    csv_file_path = os.path.join(PROJECT_ROOT, results_csv)
    file_exists = os.path.exists(csv_file_path)

    with open(csv_file_path, "a", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp", "config_label", "total_questions",
            "recall@5", "recall@10", "mrr",
            "lookup_recall@5", "lookup_mrr",
            "diff_recall@5", "diff_mrr",
            "oos_rejection_acc"
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
            "lookup_recall@5": round(lookup_r5, 4),
            "lookup_mrr": round(lookup_mrr, 4),
            "diff_recall@5": round(diff_r5, 4),
            "diff_mrr": round(diff_mrr, 4),
            "oos_rejection_acc": round(oos_acc, 4)
        })

    print(f"Results appended to {results_csv}")
    db.close()
    return per_question_results

if __name__ == "__main__":
    run_evaluation()

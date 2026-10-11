import os
import sys
import json
import re
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from main import get_ollama_embedding, SYSTEM_PROMPT
from db import DSM5Database

def strip_thinking_tags(text: str) -> str:
    """Strip any <think>...</think> reasoning traces from the model output."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Also handle unclosed <think> if any
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()

def run_pipeline():
    questions_path = os.path.join(PROJECT_ROOT, "eval", "questions.jsonl")
    output_md_path = os.path.join(PROJECT_ROOT, "try_answers.md")

    # Target 15 questions: 5 lookup, 4 vignette, 3 differential, 3 out_of_scope
    target_ids = [
        # 5 lookup
        "q01", "q03", "q05", "q07", "q12",
        # 4 vignette
        "q41", "q44", "q45", "q48",
        # 3 differential
        "q22", "q24", "q26",
        # 3 out_of_scope
        "q33", "q35", "q100"
    ]

    selected_questions = []
    with open(questions_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item["id"] in target_ids:
                    selected_questions.append(item)

    # Sort in the order of target_ids
    id_order = {qid: i for i, qid in enumerate(target_ids)}
    selected_questions.sort(key=lambda x: id_order.get(x["id"], 999))

    print(f"Loaded {len(selected_questions)} target questions. Connecting to database...")
    db = DSM5Database()

    md_output = []
    md_output.append("# DSM-5 Clinical Assistant — 15 Pipeline Verification Answers\n")
    md_output.append("Model: `qwen3:8b` (think: false, num_ctx: 8192, temperature: 0.1)\n\n---\n")

    for idx, q in enumerate(selected_questions, 1):
        qid = q["id"]
        qtype = q["type"]
        qtext = q["question"]

        print(f"[{idx}/{len(selected_questions)}] Processing {qid} ({qtype.upper()})...")

        # 1. Retrieve top-5 chunks
        query_vector = get_ollama_embedding(qtext)
        sources = db.search(query_vector, k=5)

        # 2. Build context
        context_str = ""
        for s_idx, src in enumerate(sources):
            pdf_page = src.get("pdf_page") or src.get("page_number")
            context_str += f"\n--- SOURCE {s_idx+1}: {src['disorder_name']} ({src.get('code') or 'No Code'}), p.{pdf_page}, Section: {src['section_type']} (Relevance Score: {src['score']:.4f}) ---\n"
            context_str += f"{src['content']}\n"
            context_str += "--------------------------------------------------------\n"

        full_system_prompt = f"{SYSTEM_PROMPT}\n\nRELEVANT DSM-5 REFERENCES:\n{context_str}"

        # 3. Call Ollama
        payload = {
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": qtext}
            ],
            "stream": False,
            "think": False,
            "options": {
                "num_ctx": 8192,
                "temperature": 0.1
            }
        }

        try:
            resp = requests.post("http://localhost:11434/api/chat", json=payload, timeout=90.0)
            resp.raise_for_status()
            raw_content = resp.json().get("message", {}).get("content", "")
            answer = strip_thinking_tags(raw_content)
        except Exception as e:
            answer = f"**Error generating response:** {str(e)}"

        # 4. Format Markdown block
        md_output.append(f"## {idx}. [{qid.upper()}] ({qtype.upper()})\n")
        md_output.append(f"**Question:**\n> {qtext}\n\n")
        md_output.append("### Retrieved DSM-5 Sources (Top-5):\n")
        for s_idx, src in enumerate(sources, 1):
            pdf_page = src.get("pdf_page") or src.get("page_number")
            md_output.append(
                f"- **Source {s_idx}**: `{src['disorder_name']}` | Section: `{src['section_type']}` | "
                f"Page: `p.{pdf_page}` | Score: `{src['score']:.4f}`\n"
            )
        md_output.append("\n### Assistant Response:\n")
        md_output.append(f"{answer}\n\n---\n")

    db.close()

    full_md = "".join(md_output)
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(full_md)

    print(f"\nAll 15 questions processed successfully. Output saved to {output_md_path}")

if __name__ == "__main__":
    run_pipeline()

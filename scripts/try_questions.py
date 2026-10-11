import os
import sys
import json
import re
import argparse
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from main import get_ollama_embedding, SYSTEM_PROMPT, expand_siblings
from db import DSM5Database

def strip_thinking_tags(text: str) -> str:
    """Strip any <think>...</think> reasoning traces from the model output."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()

def run_pipeline(no_context_mode: bool = False, output_path: str = None):
    questions_path = os.path.join(PROJECT_ROOT, "eval", "questions.jsonl")
    if output_path is None:
        output_path = os.path.join(PROJECT_ROOT, "try_answers.md")

    if no_context_mode:
        target_ids = ["q01", "q03", "q41"]
        print(f"\n--- RUNNING IN --no-context MODE for {target_ids} (Empty Sources) ---")
    else:
        target_ids = [
            # Lookup
            "q01", "q03", "q05", "q07", "q12",
            # Vignette
            "q41", "q44", "q45", "q48",
            # Differential (including q29)
            "q22", "q24", "q26", "q29",
            # Out-of-Scope (including q37, q39)
            "q33", "q35", "q37", "q39", "q100"
        ]
        print(f"\n--- RUNNING FULL PIPELINE FOR {len(target_ids)} TARGET QUESTIONS ---")

    selected_questions = []
    with open(questions_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item["id"] in target_ids:
                    selected_questions.append(item)

    id_order = {qid: i for i, qid in enumerate(target_ids)}
    selected_questions.sort(key=lambda x: id_order.get(x["id"], 999))

    db = None
    if not no_context_mode:
        print("Connecting to database...")
        db = DSM5Database()

    md_output = []
    if no_context_mode:
        md_output.append("\n\n# ABLATION RUN: --no-context Mode (Empty Sources)\n")
        md_output.append("Demonstrating model behavior when no DSM-5 context sources are provided.\n")
        md_output.append("Target Questions: `q01`, `q03`, `q41`\n\n---\n")
    else:
        md_output.append("# DSM-5 Clinical Assistant — Verification Answers\n")
        md_output.append("Model: `qwen3:8b` (think: false, num_ctx: 8192, temperature: 0.1)\n")
        md_output.append(f"Total Questions: {len(selected_questions)}\n\n---\n")

    for idx, q in enumerate(selected_questions, 1):
        qid = q["id"]
        qtype = q["type"]
        qtext = q["question"]

        print(f"[{idx}/{len(selected_questions)}] Processing {qid} ({qtype.upper()})...")

        if no_context_mode:
            sources = []
            context_str = "No DSM-5 references provided."
        else:
            # 1. Retrieve top-5 chunks and expand criteria/specifier siblings
            query_vector = get_ollama_embedding(qtext)
            raw_sources = db.search(query_vector, k=5)
            sources = expand_siblings(db, raw_sources)

            # 2. Build numbered context [S1]..[Sn]
            context_str = ""
            for s_idx, src in enumerate(sources, 1):
                pdf_page = src.get("pdf_page") or src.get("page_number")
                src["source_id"] = f"S{s_idx}"
                context_str += f"\n[{src['source_id']}] {src['disorder_name']} ({src.get('code') or 'No Code'}), Section: {src['section_type']}, p.{pdf_page}\n"
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

        # Validate citations
        cited_indices = [int(m) for m in re.findall(r'\[S(\d+)\]', answer)]
        max_source_idx = len(sources)
        invalid_citations = [ci for ci in cited_indices if ci < 1 or ci > max_source_idx]
        citation_warning = ""
        if invalid_citations:
            citation_warning = f"\n\n> ⚠️ **Warning:** Cited source(s) {', '.join(f'[S{i}]' for i in sorted(set(invalid_citations)))} do not exist in retrieved sources (valid: [S1]–[S{max_source_idx}])."

        # 4. Format Markdown block
        md_output.append(f"## [{qid.upper()}] ({qtype.upper()}) {'[NO-CONTEXT ABLATION]' if no_context_mode else ''}\n\n")
        md_output.append(f"**Question:**\n> {qtext}\n\n")

        if no_context_mode:
            md_output.append("### Provided Sources:\n*(None - Empty sources)*\n\n")
        else:
            md_output.append(f"### Retrieved DSM-5 Sources ({len(sources)} chunks, with Sibling Expansion):\n")
            for s_idx, src in enumerate(sources, 1):
                pdf_page = src.get("pdf_page") or src.get("page_number")
                sib_tag = " *(Sibling)*" if src.get("is_sibling") else ""
                md_output.append(
                    f"- **[S{s_idx}]**: `{src['disorder_name']}` | Section: `{src['section_type']}` | "
                    f"Page: `p.{pdf_page}` | Score: `{src['score']:.4f}`{sib_tag}\n"
                )
            md_output.append("\n")

        md_output.append("### Assistant Response:\n")
        md_output.append(f"{answer}{citation_warning}\n\n---\n\n")

    if db:
        db.close()

    result_text = "".join(md_output)
    if no_context_mode:
        # Append ablation to existing file or write separately
        if os.path.exists(output_path):
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(result_text)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result_text)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result_text)

    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSM-5 Pipeline Verification Questions Runner")
    parser.add_argument("--no-context", action="store_true", help="Run ablation with empty sources for q01, q03, q41")
    parser.add_argument("--output", default=None, help="Output markdown path")
    args = parser.parse_args()

    run_pipeline(no_context_mode=args.no_context, output_path=args.output)

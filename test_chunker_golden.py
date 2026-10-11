import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from chunker import DSM5Chunker

def test_chunker_golden():
    pdf_path = "DSM-5.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        sys.exit(1)

    chunker = DSM5Chunker(target_tokens=400, max_tokens=450)
    chunks = chunker.extract_chunks(pdf_path)

    # 1. Output disorder_names.txt with all disorder names and chunk counts
    disorder_counts = defaultdict(int)
    disorder_types = {}
    for c in chunks:
        name = c["disorder_name"]
        disorder_counts[name] += 1
        disorder_types[name] = c.get("chunk_type", "disorder")

    sorted_disorders = sorted(disorder_counts.items(), key=lambda x: x[1], reverse=True)
    with open("disorder_names.txt", "w", encoding="utf-8") as f:
        f.write(f"Total Unique Disorder/Category Names: {len(sorted_disorders)}\n")
        f.write(f"Total Chunks: {len(chunks)}\n")
        f.write("="*70 + "\n\n")
        for name, count in sorted_disorders:
            f.write(f"[{count:3d} chunks] ({disorder_types[name]:15s}) {name}\n")

    print(f"\nWrote {len(sorted_disorders)} disorder names to disorder_names.txt.")

    # 2. Golden Tests for 5 target disorders
    golden_targets = {
        "GAD": "Generalized Anxiety Disorder",
        "MDD": "Major Depressive Disorder",
        "ADHD": "Attention-Deficit/Hyperactivity Disorder",
        "PTSD": "Posttraumatic Stress Disorder",
        "Transvestic": "Transvestic Disorder"
    }

    print("\n--- Running Golden Tests for Target Disorders ---")
    for nick, expected_name in golden_targets.items():
        matched = [c for c in chunks if c["disorder_name"] == expected_name]
        assert len(matched) > 0, f"FAILED: Expected disorder '{expected_name}' not found!"
        
        # Check criteria chunk
        crit_chunks = [c for c in matched if c["section_type"] == "Diagnostic Criteria"]
        assert len(crit_chunks) > 0, f"FAILED: No Diagnostic Criteria chunk found for '{expected_name}'!"
        
        first_crit = crit_chunks[0]["content"]
        # The content has header: "{Disorder} ({code}) — Diagnostic Criteria\n\n{body}"
        # We check body starts with A.
        body = first_crit.split("— Diagnostic Criteria\n\n", 1)[-1].strip()
        # Look for Criterion A in the preamble / first criteria lines
        body_lines = [l.strip() for l in body.split("\n") if l.strip()]
        has_A = any(l.startswith("A.") or "A. " in l for l in body_lines[:6])
        print(f"[{nick}] Found {len(matched)} chunks. Criteria Chunk 0 preamble: {repr(body_lines[0][:60])}")
        assert has_A, f"FAILED: '{expected_name}' Criteria Chunk 0 does not start with Criterion A! Got: {body_lines[:4]}"

    # 3. Validation Assertions on Disorder Names
    print("\n--- Validating Disorder Name Sanitization ---")
    invalid_prefixes = ["Due to", "With", "Unspecified type"]
    failed_names = []
    for name in disorder_counts.keys():
        # Fail on names starting with lowercase
        if name and name[0].islower():
            failed_names.append((name, "starts with lowercase"))
        for bad_p in invalid_prefixes:
            if name.startswith(bad_p):
                failed_names.append((name, f"starts with '{bad_p}'"))

    if failed_names:
        print(f"FAILED: Found {len(failed_names)} invalid disorder names:")
        for fn, reason in failed_names[:10]:
            print(f"  - '{fn}': {reason}")
        assert False, f"Disorder name validation failed: {failed_names[:5]}"

    # 4. Token limit assertions
    max_tok = max(chunker.count_tokens(c["content"]) for c in chunks)
    print(f"\nMax chunk token count across all chunks: {max_tok}")
    assert max_tok <= 450, f"FAILED: Max token count {max_tok} > 450!"

    print("\n[ALL GOLDEN TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    test_chunker_golden()

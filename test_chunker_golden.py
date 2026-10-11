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

    # 2. Golden Tests for Target Disorders
    print("\n--- Running Golden Tests for Target Disorders ---")
    
    # Existing 5 target disorders
    golden_targets = {
        "GAD": "Generalized Anxiety Disorder",
        "MDD": "Major Depressive Disorder",
        "ADHD": "Attention-Deficit/Hyperactivity Disorder",
        "PTSD": "Posttraumatic Stress Disorder",
        "Transvestic": "Transvestic Disorder"
    }

    for nick, expected_name in golden_targets.items():
        matched = [c for c in chunks if c["disorder_name"] == expected_name]
        assert len(matched) > 0, f"FAILED: Expected disorder '{expected_name}' not found!"
        
        crit_chunks = [c for c in matched if c["section_type"] == "Diagnostic Criteria"]
        assert len(crit_chunks) > 0, f"FAILED: No Diagnostic Criteria chunk found for '{expected_name}'!"
        
        first_crit = crit_chunks[0]["content"]
        body = first_crit.split("— Diagnostic Criteria\n\n", 1)[-1].strip()
        body_lines = [l.strip() for l in body.split("\n") if l.strip()]
        has_A = any(l.startswith("A.") or "A. " in l for l in body_lines[:6])
        print(f"[{nick}] Found {len(matched)} chunks. Criteria Chunk 0 preamble: {repr(body_lines[0][:60])}")
        assert has_A, f"FAILED: '{expected_name}' Criteria Chunk 0 does not start with Criterion A! Got: {body_lines[:4]}"

    # New Golden Tests:
    # - Schizophrenia >= 10 chunks
    schiz_chunks = [c for c in chunks if c["disorder_name"] == "Schizophrenia"]
    print(f"[Schizophrenia] Found {len(schiz_chunks)} chunks.")
    assert len(schiz_chunks) >= 10, f"FAILED: Schizophrenia has {len(schiz_chunks)} chunks (expected >= 10)"

    # - Schizoaffective >= 5 chunks
    schizaff_chunks = [c for c in chunks if "Schizoaffective" in c["disorder_name"]]
    print(f"[Schizoaffective] Found {len(schizaff_chunks)} chunks.")
    assert len(schizaff_chunks) >= 5, f"FAILED: Schizoaffective has {len(schizaff_chunks)} chunks (expected >= 5)"

    # - Conduct Disorder >= 8 chunks
    conduct_chunks = [c for c in chunks if c["disorder_name"] == "Conduct Disorder"]
    print(f"[Conduct Disorder] Found {len(conduct_chunks)} chunks.")
    assert len(conduct_chunks) >= 8, f"FAILED: Conduct Disorder has {len(conduct_chunks)} chunks (expected >= 8)"

    # - Autism >= 12 chunks
    autism_chunks = [c for c in chunks if "Autism" in c["disorder_name"]]
    print(f"[Autism] Found {len(autism_chunks)} chunks.")
    assert len(autism_chunks) >= 12, f"FAILED: Autism has {len(autism_chunks)} chunks (expected >= 12)"

    # - Panic Disorder differential labeled Panic Disorder
    panic_diff = [c for c in chunks if c["section_type"] == "Differential Diagnosis" and c["page_number"] == 250]
    print(f"[Panic Disorder Differential] Found {len(panic_diff)} chunks on page 250.")
    assert len(panic_diff) > 0, "FAILED: No differential diagnosis chunk found for Panic Disorder on page 250!"
    for pd in panic_diff:
        assert pd["disorder_name"] == "Panic Disorder", f"FAILED: Panic Disorder differential mislabeled as '{pd['disorder_name']}'!"

    # 3. Validation Assertions on Disorder Names
    print("\n--- Validating Disorder Name Sanitization ---")
    invalid_prefixes = ["Due to", "With", "Unspecified type"]
    failed_names = []
    bad_alpha_names = []
    general_dsm5_chunks = []

    for c in chunks:
        name = c["disorder_name"]
        p_num = c["page_number"]
        
        # Alphabetic ratio check: No names with <60% alphabetic characters
        alpha_ratio = sum(ch.isalpha() for ch in name) / len(name)
        if alpha_ratio < 0.60:
            bad_alpha_names.append((name, alpha_ratio))

        # Nothing is labeled "General DSM-5" except pages before Section II
        if name == "General DSM-5" and p_num >= 67:
            general_dsm5_chunks.append((name, p_num))

    for name in disorder_counts.keys():
        if name and name[0].islower():
            failed_names.append((name, "starts with lowercase"))
        for bad_p in invalid_prefixes:
            if name.startswith(bad_p):
                failed_names.append((name, f"starts with '{bad_p}'"))

    assert len(bad_alpha_names) == 0, f"FAILED: Found disorder names with <60% alphabetic chars: {bad_alpha_names}"
    assert len(general_dsm5_chunks) == 0, f"FAILED: Found 'General DSM-5' chunks in Section II: {general_dsm5_chunks}"
    assert len(failed_names) == 0, f"FAILED: Found invalid disorder names: {failed_names}"

    # 4. Token limit assertions
    max_tok = max(chunker.count_tokens(c["content"]) for c in chunks)
    print(f"\nMax chunk token count across all chunks: {max_tok}")
    assert max_tok <= 450, f"FAILED: Max token count {max_tok} > 450!"

    print("\n[ALL GOLDEN TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    test_chunker_golden()

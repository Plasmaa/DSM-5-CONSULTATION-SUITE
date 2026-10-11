import os
import sys
import fitz
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from chunker import DSM5Chunker

def test_full_suite():
    pdf_path = "DSM-5.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        sys.exit(1)

    chunker = DSM5Chunker(target_tokens=400, max_tokens=450)
    chunks = chunker.extract_chunks(pdf_path)
    print(f"\nExtracted {len(chunks)} total chunks.")

    # 1. Update disorder_names.txt
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

    # 2. Coverage Test: Section II chunks characters vs raw Section II pages (minus running headers)
    doc = fitz.open(pdf_path)
    raw_sec2_chars = 0
    for p_idx in range(66, 832): # pages 67 to 832 inclusive
        lines = [l.strip() for l in doc[p_idx].get_text("text").split('\n') if l.strip()]
        for l in lines:
            if l.isdigit() or "Diagnostic and Statistical Manual" in l:
                continue
            cleaned = chunker.clean_text(l)
            raw_sec2_chars += len(cleaned)

    # Chunks character count (without prepended metadata headers)
    chunk_body_chars = 0
    for c in chunks:
        body = c["content"].split(" — ", 1)[-1]
        body = body.split("\n\n", 1)[-1] if "\n\n" in body else body
        chunk_body_chars += len(body)

    coverage_ratio = chunk_body_chars / raw_sec2_chars
    print(f"\n--- Coverage Test ---")
    print(f"Raw Section II body chars: {raw_sec2_chars}")
    print(f"Chunk body chars: {chunk_body_chars}")
    print(f"Coverage Ratio: {coverage_ratio:.4f}")
    assert coverage_ratio >= 0.97, f"Coverage ratio {coverage_ratio:.4f} is < 0.97!"
    print("[PASS] Coverage ratio >= 0.97")

    # 3. Page Contiguity Test: Each disorder's chunk pages form one contiguous range
    print(f"\n--- Page Contiguity Test ---")
    disorder_pages = defaultdict(list)
    for c in chunks:
        # Exclude catch-all categories that legitimately appear in multiple places
        if c["disorder_name"] in ["General DSM-5", "Section III / Emerging Measures"]:
            continue
        disorder_pages[c["disorder_name"]].append(c["page_number"])

    contiguity_violations = []
    for dis, pages in disorder_pages.items():
        pages_sorted = sorted(set(pages))
        if len(pages_sorted) > 1:
            span = pages_sorted[-1] - pages_sorted[0] + 1
            # A disorder should exist in a single contiguous chapter section (span < 25 pages, and no huge jumps > 8 pages)
            max_jump = max(b - a for a, b in zip(pages_sorted, pages_sorted[1:]))
            if max_jump > 8 or span > 30:
                contiguity_violations.append((dis, pages_sorted, max_jump))

    print(f"Contiguity violations (unrelated chapter jumps): {len(contiguity_violations)}")
    if contiguity_violations:
        for dis, pages, gap in contiguity_violations[:5]:
            print(f"  - {dis}: pages {pages} (max_jump={gap})")
    assert len(contiguity_violations) == 0, f"Disorder page contiguity violated: {contiguity_violations[:3]}"
    print("[PASS] Disorder chunk pages form contiguous ranges!")

    # 4. Golden Tests: MDD >= 15, ADHD >= 8, each has Differential Diagnosis and Comorbidity
    print(f"\n--- Golden Tests: MDD & ADHD ---")
    mdd_chunks = [c for c in chunks if c["disorder_name"] == "Major Depressive Disorder"]
    adhd_chunks = [c for c in chunks if c["disorder_name"] == "Attention-Deficit/Hyperactivity Disorder"]

    print(f"MDD chunk count: {len(mdd_chunks)}")
    print(f"ADHD chunk count: {len(adhd_chunks)}")

    assert len(mdd_chunks) >= 15, f"MDD has only {len(mdd_chunks)} chunks, expected >= 15!"
    assert len(adhd_chunks) >= 8, f"ADHD has only {len(adhd_chunks)} chunks, expected >= 8!"

    mdd_sections = {c["section_type"] for c in mdd_chunks}
    adhd_sections = {c["section_type"] for c in adhd_chunks}

    assert "Differential Diagnosis" in mdd_sections, "MDD missing Differential Diagnosis!"
    assert "Comorbidity" in mdd_sections, "MDD missing Comorbidity!"
    assert "Differential Diagnosis" in adhd_sections, "ADHD missing Differential Diagnosis!"
    assert "Comorbidity" in adhd_sections, "ADHD missing Comorbidity!"
    print("[PASS] MDD and ADHD have >= target chunks and contain Differential Diagnosis & Comorbidity!")

    # 5. Golden Tests: GAD, PTSD, Transvestic & Strict Criteria A-H for PTSD
    print(f"\n--- Golden Tests: GAD, PTSD, Transvestic ---")
    ptsd_chunks = [c for c in chunks if c["disorder_name"] == "Posttraumatic Stress Disorder"]
    ptsd_crit_text = "\n".join(c["content"] for c in ptsd_chunks if c["section_type"] == "Diagnostic Criteria")
    for crit_letter in ["A.", "B.", "C.", "D.", "E.", "F.", "G.", "H."]:
        assert crit_letter in ptsd_crit_text, f"PTSD criteria missing Criterion {crit_letter}!"
    print("[PASS] PTSD criteria A through H all present!")

    gad_chunks = [c for c in chunks if c["disorder_name"] == "Generalized Anxiety Disorder"]
    assert len(gad_chunks) >= 8, f"GAD has {len(gad_chunks)} chunks!"
    trans_chunks = [c for c in chunks if c["disorder_name"] == "Transvestic Disorder"]
    assert len(trans_chunks) >= 5, f"Transvestic Disorder has {len(trans_chunks)} chunks!"
    print("[PASS] GAD and Transvestic Disorder golden checks passed!")

    print("\n[ALL 5 REQUISITE TESTS PASSED COMPLETELY!]")

if __name__ == "__main__":
    test_full_suite()

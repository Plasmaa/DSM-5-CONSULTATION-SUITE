import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from chunker import DSM5Chunker

def run_chunker_audit():
    pdf_path = "DSM-5.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        sys.exit(1)

    chunker = DSM5Chunker(target_tokens=400, max_tokens=450)
    chunks = chunker.extract_chunks(pdf_path)

    print("\n--- Auditing Produced Chunks ---")
    print(f"Total chunks produced: {len(chunks)}")

    token_counts = []
    oversized = []

    for c in chunks:
        toks = chunker.count_tokens(c["content"])
        token_counts.append((c, toks))
        if toks > 450:
            oversized.append((c, toks))

    token_counts.sort(key=lambda x: x[1], reverse=True)

    print("\nTop 20 Largest Chunks:")
    for c, toks in token_counts[:20]:
        print(f"[{toks} tokens] P{c['page_number']} | {c['disorder_name']} ({c['section_type']}) - Chunk {c['chunk_index']}")

    avg_toks = sum(t[1] for t in token_counts) / len(token_counts)
    print(f"\nAverage token count: {avg_toks:.1f}")
    print(f"Max token count: {token_counts[0][1]}")
    print(f"Min token count: {token_counts[-1][1]}")
    print(f"Chunks exceeding 450 tokens: {len(oversized)}")

    # Sanity Assertions
    assert len(oversized) == 0, f"Found {len(oversized)} chunks exceeding 450 tokens!"
    assert token_counts[0][1] <= 450, f"Max tokens {token_counts[0][1]} exceeds 450!"
    print("\n[PASS] All chunks are strictly <= 450 tokens!")

if __name__ == "__main__":
    run_chunker_audit()

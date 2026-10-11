import sqlite3
import requests
from transformers import AutoTokenizer

def check_chunks():
    print("Loading BAAI/bge-large-en-v1.5 tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-large-en-v1.5")
    except Exception as e:
        print("Could not load from huggingface directly, trying bert-base-uncased:", e)
        tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

    conn = sqlite3.connect("dsm5_cache.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, disorder_name, section_type, content FROM chunks")
    rows = cursor.fetchall()
    
    over_512 = []
    token_counts = []
    
    for cid, dis, sec, content in rows:
        tokens = len(tokenizer.encode(content, add_special_tokens=True))
        token_counts.append(tokens)
        if tokens > 512:
            over_512.append((cid, dis, sec, tokens))
            
    print(f"\n--- Chunk Token Analysis ---")
    print(f"Total chunks in cache: {len(rows)}")
    if token_counts:
        print(f"Max token count: {max(token_counts)}")
        print(f"Min token count: {min(token_counts)}")
        print(f"Average token count: {sum(token_counts)/len(token_counts):.1f}")
    print(f"Chunks exceeding 512 tokens: {len(over_512)} ({len(over_512)/len(rows)*100:.1f}%)")
    
    if over_512:
        print("\nTop 10 largest chunks:")
        over_512.sort(key=lambda x: x[3], reverse=True)
        for cid, dis, sec, tokens in over_512[:10]:
            print(f"  - [{cid}] {dis} ({sec}): {tokens} tokens")

if __name__ == "__main__":
    check_chunks()

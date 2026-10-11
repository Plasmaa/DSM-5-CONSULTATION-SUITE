import os
import sys
import time
from chunker import DSM5Chunker
from db import DSM5Database
from sentence_transformers import SentenceTransformer

def run_indexing():
    pdf_path = "DSM-5.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file '{pdf_path}' not found in the workspace.")
        sys.exit(1)

    print("--- Starting DSM-5 Indexing Pipeline ---")
    
    # 1. Initialize Database & Connect to Pinecone
    print("\nInitializing database connection...")
    db = DSM5Database()
    if not db.api_key:
        print("Error: PINECONE_API_KEY is not configured.")
        print("Please create a '.env' file in the root directory containing:")
        print("PINECONE_API_KEY=your_actual_key_here")
        sys.exit(1)
        
    if not db.index:
        print("Error: Could not connect to Pinecone index. Please check your API key and network connection.")
        sys.exit(1)

    # 2. Extract and Chunk PDF
    start_time = time.time()
    print("\nParsing and chunking PDF... (this may take a minute)")
    chunker = DSM5Chunker()
    chunks = chunker.extract_chunks(pdf_path)
    
    if not chunks:
        print("Error: No chunks extracted from PDF. Check parser logic.")
        sys.exit(1)

    # Validate chunk ID uniqueness
    chunk_ids = [c["id"] for c in chunks]
    unique_ids = set(chunk_ids)
    assert len(chunk_ids) == len(unique_ids), (
        f"Duplicate chunk IDs detected! {len(chunk_ids)} total chunks, "
        f"but only {len(unique_ids)} unique IDs ({len(chunk_ids) - len(unique_ids)} duplicates). Aborting."
    )
    print(f"Verified {len(chunks)} chunks with 100% unique IDs.")

    # 3. Generate Embeddings via Ollama
    print("\nGenerating embeddings for chunks via local Ollama (bge-large)...")
    texts = [c["content"] for c in chunks]
    
    import requests
    
    def get_ollama_embeddings_batch(texts, batch_size=100):
        url = "http://localhost:11434/api/embed"
        all_embeddings = []
        
        # Process in batches to avoid payload size issues
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"Embedding batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}... ", end="", flush=True)
            batch_start = time.time()
            try:
                response = requests.post(url, json={
                    "model": "bge-large",
                    "input": batch,
                    "truncate": False
                }, timeout=60.0)
                
                if response.status_code == 200:
                    all_embeddings.extend(response.json()["embeddings"])
                    print(f"done in {time.time() - batch_start:.2f}s")
                else:
                    raise Exception(f"Ollama embedding failed with status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"failed: {e}. Trying legacy fallback for this batch...")
                # Fallback to legacy individual embeddings API
                legacy_url = "http://localhost:11434/api/embeddings"
                for text in batch:
                    resp = requests.post(legacy_url, json={
                        "model": "bge-large",
                        "prompt": text
                    }, timeout=10.0)
                    resp.raise_for_status()
                    all_embeddings.append(resp.json()["embedding"])
                print(f"done (legacy fallback) in {time.time() - batch_start:.2f}s")
                
        return all_embeddings

    embed_start = time.time()
    embeddings = get_ollama_embeddings_batch(texts, batch_size=100)
    embed_end = time.time()
    print(f"Generated {len(embeddings)} embeddings in {embed_end - embed_start:.2f} seconds.")

    db.upsert_chunks(chunks, embeddings)
    
    end_time = time.time()
    print("\n--- Indexing Completed Successfully! ---")
    print(f"Total Chunks Indexed: {len(chunks)}")
    print(f"Total Time Taken: {end_time - start_time:.2f} seconds.")
    
    # Print status report
    stats = db.get_status()
    print(f"SQLite Count: {stats['sqlite_count']}")
    print(f"Pinecone Vector Count: {stats['pinecone_vector_count']}")
    
    db.close()

if __name__ == "__main__":
    run_indexing()

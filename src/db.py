import os
import sqlite3
from pinecone import Pinecone, ServerlessSpec

# Database configuration
SQLITE_DB_PATH = "dsm5_cache.db"
INDEX_NAME = "dsm5-index"

class DSM5Database:
    def __init__(self):
        self.api_key = self._load_api_key()
        if not self.api_key:
            print("WARNING: PINECONE_API_KEY not found in environment or .env file. RAG search will not work until set.")
        
        self.pc = Pinecone(api_key=self.api_key) if self.api_key else None
        self._init_sqlite()
        self._init_pinecone()

    def _load_api_key(self):
        """Load Pinecone API key from environment or a local .env file."""
        api_key = os.environ.get("PINECONE_API_KEY")
        if api_key:
            return api_key

        # Try to read from local .env
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PINECONE_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        return None

    def _init_sqlite(self):
        """Create the local SQLite cache database and tables."""
        self.conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                disorder_name TEXT,
                code TEXT,
                section_type TEXT,
                content TEXT NOT NULL,
                page_number INTEGER
            )
        """)
        self.conn.commit()

    def _init_pinecone(self):
        """Ensure the Pinecone index exists and is connected."""
        if not self.pc:
            return

        try:
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            if INDEX_NAME not in existing_indexes:
                print(f"Creating Pinecone index '{INDEX_NAME}'...")
                self.pc.create_index(
                    name=INDEX_NAME,
                    dimension=1024,  # BAAI/bge-large-en-v1.5 dimension
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
                print(f"Pinecone index '{INDEX_NAME}' created successfully.")
            self.index = self.pc.Index(INDEX_NAME)
        except Exception as e:
            print(f"Error initializing Pinecone: {e}")
            self.index = None

    def get_status(self):
        """Return database indexing statistics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunks")
        sqlite_count = cursor.fetchone()[0]

        pinecone_ready = False
        vector_count = 0
        if self.pc and self.index:
            try:
                stats = self.index.describe_index_stats()
                vector_count = stats.total_vector_count
                pinecone_ready = True
            except Exception:
                pass

        return {
            "sqlite_count": sqlite_count,
            "pinecone_ready": pinecone_ready,
            "pinecone_vector_count": vector_count,
            "index_name": INDEX_NAME
        }

    def upsert_chunks(self, chunks, embeddings):
        """Upsert chunks metadata to SQLite and embeddings to Pinecone."""
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings length must match")

        # 1. Save to SQLite
        cursor = self.conn.cursor()
        sqlite_records = [
            (c["id"], c["disorder_name"], c["code"], c["section_type"], c["content"], c["page_number"])
            for c in chunks
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO chunks (id, disorder_name, code, section_type, content, page_number)
            VALUES (?, ?, ?, ?, ?, ?)
        """, sqlite_records)
        self.conn.commit()

        # 2. Upsert to Pinecone
        if self.pc and self.index:
            vectors_to_upsert = []
            for i, chunk in enumerate(chunks):
                # Storing minimal metadata in Pinecone, full text retrieved from SQLite
                vectors_to_upsert.append({
                    "id": chunk["id"],
                    "values": embeddings[i],
                    "metadata": {
                        "disorder_name": chunk["disorder_name"] or "",
                        "section_type": chunk["section_type"] or ""
                    }
                })

            # Upsert in batches of 100
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch = vectors_to_upsert[i:i + batch_size]
                self.index.upsert(vectors=batch)
            print(f"Upserted {len(chunks)} vectors to Pinecone.")
        else:
            print("Pinecone client not initialized. Skipped Pinecone upload.")

    def search(self, query_vector, k=5, filter_disorder=None):
        """Search vector database and return matching text chunks from SQLite."""
        if not self.pc or not self.index:
            raise RuntimeError("Pinecone is not initialized. Please verify your API key.")

        # Search Pinecone
        try:
            # Prepare filter if disorder boosting/filtering is requested
            pinecone_filter = None
            if filter_disorder:
                pinecone_filter = {"disorder_name": {"$eq": filter_disorder}}

            results = self.index.query(
                vector=query_vector,
                top_k=k,
                include_metadata=True,
                filter=pinecone_filter
            )
        except Exception as e:
            print(f"Error querying Pinecone: {e}")
            return []

        # Fetch matched records from SQLite
        ids = [match.id for match in results.matches]
        if not ids:
            return []

        # Keep original Pinecone ordering by scoring
        scores_map = {match.id: match.score for match in results.matches}

        cursor = self.conn.cursor()
        # Safe parameterized IN clause
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(f"""
            SELECT id, disorder_name, code, section_type, content, page_number
            FROM chunks
            WHERE id IN ({placeholders})
        """, ids)
        records = cursor.fetchall()

        retrieved = []
        for r in records:
            retrieved.append({
                "id": r[0],
                "disorder_name": r[1],
                "code": r[2],
                "section_type": r[3],
                "content": r[4],
                "page_number": r[5],
                "score": scores_map.get(r[0], 0.0)
            })

        # Sort results by Pinecone score (highest first)
        retrieved.sort(key=lambda x: x["score"], reverse=True)
        return retrieved

    def close(self):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from db import DSM5Database

def wipe_all():
    print("--- Wiping Pinecone and SQLite ---")
    db = DSM5Database()
    if db.index:
        try:
            stats = db.index.describe_index_stats()
            print(f"Current Pinecone stats: {stats}")
            if stats.total_vector_count > 0:
                print("Deleting all vectors from Pinecone...")
                db.index.delete(delete_all=True)
                print("Pinecone vectors deleted.")
            else:
                print("Pinecone index is already empty.")
        except Exception as e:
            print(f"Pinecone delete note: {e}")
    else:
        print("Pinecone index not connected.")

    # Wipe SQLite
    print("Clearing SQLite database tables...")
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM chunks")
    db.conn.commit()
    cursor.execute("VACUUM")
    db.conn.commit()
    print("SQLite chunks table cleared and vacuumed.")

    status = db.get_status()
    print(f"Post-wipe status: SQLite count = {status['sqlite_count']}, Pinecone vector count = {status['pinecone_vector_count']}")
    db.close()

if __name__ == "__main__":
    wipe_all()

import json
import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db import DSM5Database

# Initialize FastAPI
app = FastAPI(title="DSM-5 Chief Psychiatrist Consultation Suite")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for DB
db = None

def get_ollama_embedding(text: str) -> List[float]:
    """Call Ollama embeddings API locally."""
    import requests
    url = "http://localhost:11434/api/embeddings"
    response = requests.post(url, json={
        "model": "bge-large",
        "prompt": text
    }, timeout=10.0)
    response.raise_for_status()
    return response.json()["embedding"]

@app.on_event("startup")
def startup_event():
    global db
    print("Initializing Database...")
    db = DSM5Database()
    print("FastAPI ready and using Ollama for embeddings.")

@app.on_event("shutdown")
def shutdown_event():
    global db
    if db:
        db.close()

# Pydantic models for request validation
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "qwen2.5:7b"

class RetrieveRequest(BaseModel):
    query: str
    k: Optional[int] = 5
    filter_disorder: Optional[str] = None

# "Boss Psychiatrist" System Prompt
SYSTEM_PROMPT = """You are the Chief of Clinical Psychiatry, a world-renowned, elite medical director. You speak with absolute authority, clinical precision, and directness. You cut through vagueness, diagnose strictly by the DSM-5 criteria, and speak like a seasoned, confident medical director who runs the ward.

Your task is to analyze the patient's presentation or answer the user's clinical inquiry based ONLY on the provided DSM-5 sections.

Rules of Engagement:
1. Persona: Speak like a decisive, analytical, and highly knowledgeable Chief of Psychiatry. Be confident and authoritative. 
2. Grounding: Rely strictly on the provided DSM-5 source chunks. If the answer cannot be found in the provided sources, explicitly state: "That information is not present in my DSM-5 reference material." Never hallucinate or use external psychiatric criteria.
3. Citations: Cite your sources inline. Cite the disorder name, ICD code, and PDF page numbers whenever you refer to diagnostic criteria or symptoms. Format citations exactly like this: [Major Depressive Disorder, 296.22 (F32.1), Page 160].
4. Diagnostics: If the user provides a case description, outline the diagnostic criteria met, check for required symptoms, and highlight differentials (e.g. Bipolar I vs Bipolar II) or comorbidity options based on the texts. If details are missing to confirm a diagnosis, ask the user (in a commanding, clinical manner) for those specific symptoms.
"""

@app.get("/api/status")
async def get_status():
    """Return indexing stats and check Ollama's availability."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Check Ollama connection
    ollama_running = False
    downloaded_models = []
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                ollama_running = True
                data = response.json()
                downloaded_models = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    db_stats = db.get_status()
    return {
        "sqlite_count": db_stats["sqlite_count"],
        "pinecone_ready": db_stats["pinecone_ready"],
        "pinecone_vector_count": db_stats["pinecone_vector_count"],
        "index_name": db_stats["index_name"],
        "ollama_running": ollama_running,
        "ollama_models": downloaded_models
    }

@app.post("/api/retrieve")
async def retrieve_chunks(req: RetrieveRequest):
    """Accept a query, generate local embeddings, and search Pinecone."""
    if not db:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    try:
        # Generate query vector
        query_vector = get_ollama_embedding(req.query)
        # Search Pinecone + SQLite
        matches = db.search(query_vector, k=req.k, filter_disorder=req.filter_disorder)
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Conversational RAG endpoint using Server-Sent Events (SSE)."""
    if not db:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    # 1. Extract the last user message
    user_messages = [msg for msg in req.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found in history")
    
    last_query = user_messages[-1].content

    # 2. Retrieve relevant DSM-5 chunks
    try:
        query_vector = get_ollama_embedding(last_query)
        sources = db.search(query_vector, k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sources: {str(e)}")

    # 3. Build context for the LLM
    context_str = ""
    for idx, src in enumerate(sources):
        context_str += f"\n--- SOURCE {idx+1}: {src['disorder_name']} ({src['code'] or 'No Code'}), Page {src['page_number']}, Section: {src['section_type']} (Relevance Score: {src['score']:.4f}) ---\n"
        context_str += f"{src['content']}\n"
        context_str += "--------------------------------------------------------\n"

    # 4. Prepare messages for Ollama
    # System message includes the grounding instructions + retrieved DSM-5 context
    full_system_prompt = f"{SYSTEM_PROMPT}\n\nRELEVANT DSM-5 REFERENCES:\n{context_str}"
    
    ollama_messages = [{"role": "system", "content": full_system_prompt}]
    
    # Add conversation history (excluding any previous system prompt injections)
    for msg in req.messages:
        ollama_messages.append({"role": msg.role, "content": msg.content})

    # 5. Define SSE Generator
    async def sse_generator():
        # First send the retrieved sources list to the client
        # Clean sources from full content text for lightweight header transmission
        light_sources = []
        for src in sources:
            light_sources.append({
                "disorder_name": src["disorder_name"],
                "code": src["code"],
                "section_type": src["section_type"],
                "page_number": src["page_number"],
                "score": src["score"],
                "content": src["content"] # include text so they can read details in drawer
            })
        yield f"data: {json.dumps({'type': 'sources', 'sources': light_sources})}\n\n"

        # Call Ollama API in streaming mode
        ollama_payload = {
            "model": req.model,
            "messages": ollama_messages,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST", 
                    "http://localhost:11434/api/chat", 
                    json=ollama_payload
                ) as response:
                    if response.status_code != 200:
                        yield f"data: {json.dumps({'type': 'error', 'error': 'Ollama responded with status code ' + str(response.status_code)})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            delta = data.get("message", {}).get("content", "")
                            if delta:
                                yield f"data: {json.dumps({'type': 'content', 'delta': delta})}\n\n"
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': f'Connection to Ollama failed: {str(e)}'})}\n\n"

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

# Serve SPA
@app.get("/")
def read_root():
    return FileResponse("public/index.html")

# Mount public directory for static files (CSS, JS, assets)
# Note: Mount at the end to avoid conflict with API endpoints
if os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public"), name="public")

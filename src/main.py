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
    """Call Ollama embeddings API locally using modern /api/embed endpoint with legacy fallback."""
    import requests
    url = "http://localhost:11434/api/embed"
    try:
        response = requests.post(url, json={
            "model": "bge-large",
            "input": text
        }, timeout=10.0)
        if response.status_code == 200:
            return response.json()["embeddings"][0]
    except Exception:
        pass

    # Fallback to legacy endpoint if /api/embed is unavailable
    legacy_url = "http://localhost:11434/api/embeddings"
    response = requests.post(legacy_url, json={
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

class ThinkTagFilter:
    """Filter out <think>...</think> reasoning tags from streaming token deltas."""
    def __init__(self):
        self.in_think = False
        self.buffer = ""

    def process(self, chunk: str) -> str:
        self.buffer += chunk
        out = ""
        while self.buffer:
            if not self.in_think:
                start_idx = self.buffer.find("<think>")
                if start_idx != -1:
                    out += self.buffer[:start_idx]
                    self.buffer = self.buffer[start_idx + len("<think>"):]
                    self.in_think = True
                else:
                    matched_prefix = False
                    for i in range(1, min(len("<think>"), len(self.buffer) + 1)):
                        if "<think>".startswith(self.buffer[-i:]):
                            out += self.buffer[:-i]
                            self.buffer = self.buffer[-i:]
                            matched_prefix = True
                            break
                    if not matched_prefix:
                        out += self.buffer
                        self.buffer = ""
                    else:
                        break
            else:
                end_idx = self.buffer.find("</think>")
                if end_idx != -1:
                    self.buffer = self.buffer[end_idx + len("</think>"):].lstrip()
                    self.in_think = False
                else:
                    matched_prefix = False
                    for i in range(1, min(len("</think>"), len(self.buffer) + 1)):
                        if "</think>".startswith(self.buffer[-i:]):
                            self.buffer = self.buffer[-i:]
                            matched_prefix = True
                            break
                    if not matched_prefix:
                        self.buffer = ""
                    break
        return out

    def flush(self) -> str:
        if not self.in_think:
            res = self.buffer
            self.buffer = ""
            return res
        self.buffer = ""
        return ""

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "qwen3:8b"

class RetrieveRequest(BaseModel):
    query: str
    k: Optional[int] = 5
    filter_disorder: Optional[str] = None

# Reference Assistant System Prompt
SYSTEM_PROMPT = """You are a reference assistant for clinicians. Answer ONLY from the provided DSM-5 sources. Quote criteria faithfully. Cite as [Disorder, Section, p.X]. If the sources don't contain the answer, say 'Not found in the retrieved DSM-5 sections.' Do not diagnose individual patients."""

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

    # 2. Retrieve relevant DSM-5 chunks (no score cutoff)
    try:
        query_vector = get_ollama_embedding(last_query)
        sources = db.search(query_vector, k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sources: {str(e)}")

    # 3. Build context for the LLM
    context_str = ""
    for idx, src in enumerate(sources):
        pdf_page = src.get("pdf_page") or src.get("page_number")
        context_str += f"\n--- SOURCE {idx+1}: {src['disorder_name']} ({src.get('code') or 'No Code'}), p.{pdf_page}, Section: {src['section_type']} (Relevance Score: {src['score']:.4f}) ---\n"
        context_str += f"{src['content']}\n"
        context_str += "--------------------------------------------------------\n"

    # 4. Prepare messages for Ollama
    full_system_prompt = f"{SYSTEM_PROMPT}\n\nRELEVANT DSM-5 REFERENCES:\n{context_str}"
    
    ollama_messages = [{"role": "system", "content": full_system_prompt}]
    
    # Add conversation history
    for msg in req.messages:
        ollama_messages.append({"role": msg.role, "content": msg.content})

    # 5. Define SSE Generator
    async def sse_generator():
        # Send retrieved sources metadata to client
        light_sources = []
        for src in sources:
            pdf_page = src.get("pdf_page") or src.get("page_number")
            light_sources.append({
                "disorder_name": src["disorder_name"],
                "code": src["code"],
                "section_type": src["section_type"],
                "page_number": pdf_page,
                "pdf_page": pdf_page,
                "score": src["score"],
                "content": src["content"]
            })
        yield f"data: {json.dumps({'type': 'sources', 'sources': light_sources})}\n\n"

        # Call Ollama API in streaming mode with think: false, num_ctx: 8192, temperature: 0.1
        ollama_payload = {
            "model": req.model,
            "messages": ollama_messages,
            "stream": True,
            "think": False,
            "options": {
                "num_ctx": 8192,
                "temperature": 0.1
            }
        }
        
        think_filter = ThinkTagFilter()
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
                            raw_delta = data.get("message", {}).get("content", "")
                            if raw_delta:
                                filtered_delta = think_filter.process(raw_delta)
                                if filtered_delta:
                                    yield f"data: {json.dumps({'type': 'content', 'delta': filtered_delta})}\n\n"
                        except json.JSONDecodeError:
                            continue

                    final_delta = think_filter.flush()
                    if final_delta:
                        yield f"data: {json.dumps({'type': 'content', 'delta': final_delta})}\n\n"
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

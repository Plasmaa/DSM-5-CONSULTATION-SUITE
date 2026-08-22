# DSM-5 RAG — Build Plan

A retrieval-augmented generation system over the DSM-5, running fully local.

## Stack

| Component | Choice | Why |
|---|---|---|
| PDF extraction | `PyMuPDF` (fitz) | Best layout/heading fidelity for text-layer PDFs |
| Chunking | Custom structure-aware parser | DSM-5 has real hierarchy (disorder → criteria → specifiers); fixed-size chunking breaks criteria lists apart |
| Embedding model | `BAAI/bge-large-en-v1.5` via `sentence-transformers` | Strong MTEB retrieval score, runs local on GPU, free |
| Vector store | PostgreSQL + `pgvector` | Reuses existing Postgres skillset, no new DB to learn |
| LLM | Llama 3.1 8B (Q4_K_M) or Qwen2.5 7B via **Ollama** | Fits in 6GB VRAM, fully local, no API cost |
| Reranker (stretch) | `bge-reranker-base` | Cross-encoder rerank of top-k before generation — DSM-5 has near-duplicate phrasing across disorders that confuses pure cosine similarity |
| Backend | FastAPI | Orchestrates retrieve → (rerank) → generate |
| Frontend | React (plain, no build step — same pattern as filesync project) | Simple chat UI |

## Build Order

Build in this order so each stage is independently testable before the next depends on it.

### Step 1 — Extract & Inspect
- Load the DSM-5 PDF with PyMuPDF.
- Dump raw extracted text for a few known sections (pick 2-3 disorders you know well) and manually inspect:
  - Is it a real text layer, or does it need OCR?
  - How are headings/section breaks represented (font size changes? bold? consistent prefixes like "Diagnostic Criteria")?
  - Are there running headers/footers/page numbers polluting the text that need stripping?
- **Output of this step**: a short note on the PDF's actual structure — this determines how step 2 is written. Don't write the chunker until you've looked at real extracted text.

### Step 2 — Structure-Aware Chunking
- Parse the document into a hierarchy: `Disorder → {Diagnostic Criteria, Specifiers, Differential Diagnosis, Prevalence, ...}`.
- Each chunk = one disorder's full criteria block (or one subsection if a disorder's section is long — don't split a criteria list itself).
- Attach metadata to every chunk:
  ```json
  {
    "disorder_name": "...",
    "code": "...",       // DSM/ICD code if present
    "section_type": "criteria" | "specifiers" | "differential_diagnosis" | "prevalence" | "other"
  }
  ```
- Validate: manually spot-check ~10 chunks against the source PDF to confirm no criteria got split mid-list.

### Step 3 — Embedding & Storage
- Set up Postgres with the `pgvector` extension: `CREATE EXTENSION vector;`
- Schema:
  ```sql
  CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    disorder_name TEXT,
    code TEXT,
    section_type TEXT,
    content TEXT NOT NULL,
    embedding VECTOR(1024)  -- bge-large-en-v1.5 dimension
  );
  CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);
  ```
- Batch-embed all chunks with `bge-large-en-v1.5` on GPU, insert into the table.

### Step 4 — Retrieval-Only Endpoint (no LLM yet)
- FastAPI endpoint: `POST /retrieve { query }` → embed query → cosine similarity search → return top-k chunks with metadata.
- **Add hybrid filtering**: if the query text matches a known disorder name, filter/boost to that disorder's chunks before falling back to pure vector search.
- Test with real queries and confirm the right chunks come back *before* touching generation — this isolates retrieval quality from generation quality.

### Step 5 — Generation
- Install Ollama, pull `llama3.1:8b` (or `qwen2.5:7b`).
- FastAPI endpoint: `POST /ask { query }` → retrieve top-k chunks → build prompt → call Ollama → return answer + cited source chunks.
- System prompt must force the model to:
  - Answer only from the provided context chunks.
  - Cite which disorder/section each part of the answer came from.
  - Explicitly say "not in the provided context" if the answer isn't supported — don't let it fall back on parametric knowledge.

### Step 6 — Reranking (stretch goal)
- After initial vector retrieval returns top-20, rerank with `bge-reranker-base` cross-encoder, take top-5 for generation.
- Compare answer quality with/without reranking on a fixed test query set — write down the difference, it's a good project writeup point.

### Step 7 — Frontend
- Simple chat UI (React, no build step, same pattern as the filesync project): input box, message history, and expandable "sources" panel per answer showing which chunks were retrieved.

## Open Decisions To Confirm Before Coding

- [ ] Confirm PDF is a real text layer (not scanned) — determines if OCR is needed
- [ ] Confirm heading pattern for the chunker after inspecting real extracted text
- [ ] Decide chunk size ceiling for unusually long disorder sections (when to split within a disorder)
- [ ] Decide k (number of chunks retrieved) and whether reranking is in v1 or a stretch goal

## Notes
- Keep the DSM-5 PDF and any extracted text local — don't send it to third-party APIs. This is part of the design rationale (fully local stack), not just a cost decision.
- Test queries worth keeping as a fixed eval set: pick ~10 questions spanning "what are the criteria for X", "differential diagnosis of X vs Y", "prevalence of X" — reuse these across every pipeline change so you can tell if a change actually improved things.

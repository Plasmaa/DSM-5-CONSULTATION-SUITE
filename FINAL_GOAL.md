# DSM-5 Clinical Reference RAG Suite — Final Architecture & Roadmap (v2.0)

## 1. Executive Summary & Project Goal
The **DSM-5 Clinical Consultation Suite** is an offline-capable, high-precision clinical **reference assistant** designed for psychiatrists and mental health practitioners. It is explicitly a **reference tool** (not an automated diagnostic engine), grounded strictly in the official American Psychiatric Association (APA) DSM-5 manual.

### Primary Purpose
To serve as an **AI-Engineer showcase portfolio project** demonstrating rigorous, empirical search engineering. Rather than simply chaining an LLM to a vector database, this project emphasizes:
- Controlled ablation studies where every configuration is benchmarked.
- Deterministic ground-truth evaluation metrics recorded in `results.csv`.
- Clinical safety guardrails (rejection of out-of-scope inquiries and crisis intervention protocols).
- Ultra-fast local-first execution powered by consumer hardware (RTX 5060 8GB VRAM / 16GB RAM).

---

## 2. Target Production Architecture

```
                  +----------------------------------------------+
                  |         Vanilla JS / CSS Web Interface       |
                  |  - SSE Streaming Chat & Diagnostic Drawer    |
                  |  - Interactive Interactive Citation Linking  |
                  |  - Real-Time Retrieval Metadata & Confidence |
                  +----------------------+-----------------------+
                                         |
                                  HTTP / SSE (FastAPI)
                                         |
                                         v
+--------------------------------------------------------------------------------+
|                             FastAPI Backend Service                            |
|                                                                                |
|  1. Input Guardrails: Crisis Keyword Filter & Out-Of-Scope Detection           |
|  2. Retrieval Coordinator: Hybrid Search + Cross-Encoder Reranker              |
|  3. Clinical Grounding Prompter: Citation Enforcement & Refusal Formatter      |
|  4. Streaming Response Engine: Server-Sent Events (SSE)                        |
+----------------------+---------------------------------+-----------------------+
                       |                                 |
                       v                                 v
+---------------------------------------+   +------------------------------------+
|            Qdrant Vector DB           |   |       Ollama Inference Engine      |
|           (Local Docker Container)    |   |         (RTX 5060 Local GPU)       |
|                                       |   |                                    |
| - Dedicated Named Collections:        |   | - Embedders:                       |
|   * `dsm5_bge_large` (1024-dim dense) |   |   * `bge-large` (1024d)            |
|   * `dsm5_bge_m3`    (1024d/multi)    |   |   * `bge-m3`                       |
|   * `dsm5_qwen3_emb` (dense/sparse)   |   |   * `qwen3-embedding`              |
| - Integrated BM25 Sparse Inverted Index|  | - LLM Generator:                   |
| - Payload storage (Disorder, Section, |   |   * `qwen3:8b` (Thinking On/Off)   |
|   Page, Chunk Index, Full Content)    |   |   * Context Window: 8192 tokens    |
+---------------------------------------+   +------------------------------------+
                       ^
                       |
+----------------------+---------------------------------------------------------+
|                  FlashRank / BGE Cross-Encoder Reranker                        |
|                                                                                |
| - In-memory reranking of top 20–30 retrieved candidates down to top 5 chunks  |
| - Context score compression & confidence gating (rejects irrelevant content)   |
+--------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Breakdown

### 3.1. Document Ingestion & Chunking Engine (`src/chunker.py`)
- **Semantic Section Boundary Parsing**:
  - Enforces strict termination using font size and formatting metadata extracted via `page.get_text("dict")`.
  - Captures primary disorders (`15.0pt`–`19.4pt` bold text) and distinct subsections (`Diagnostic Criteria`, `Prevalence`, `Differential Diagnosis`, `Comorbidity`).
  - Separates non-disorder content: front matter (< page 67) and the 130-page back index/appendices ($\ge$ page 833) are excluded or labeled distinctly.
  - Recognizes residual disorders (*"Other Specified..."* and *"Unspecified..."*) as distinct entities, preventing section leakage into subsequent chapters.
- **Token-Aware Hierarchical Sub-Splitter**:
  - Enforces a strict ceiling of **$\le$ 450 tokens** per chunk (target: ~400 tokens) with `truncate: False` enforced in Ollama.
  - Respects clinical criteria boundaries: Criterion items (`A.`, `B.`, `C.`, etc.) are kept intact and never split mid-sentence.
  - Automatically prepends metadata context: `{Disorder Name} ({ICD Code}) — {Section Type}` to every chunk, with token usage accounted for in the budget.
  - Merges tiny fragment sub-chunks (< 60 tokens) back into their preceding sibling.
  - Deterministic IDs: MD5 seed using `{Disorder}_{Section}_{Page}_chunk{Index}` to prevent collisions.

### 3.2. Storage Layer: Migration to Qdrant (Docker)
- **Elimination of SQLite Dependency**:
  - Drops the dual Pinecone + SQLite setup.
  - Stores all chunk payloads directly inside Qdrant points (disorder name, ICD code, section type, page number, chunk index, full content text).
- **Multi-Collection Architecture**:
  - Isolates experiments into independent, parallel collections:
    1. `dsm5_bge_large` (Baseline 1024-dim dense).
    2. `dsm5_bge_m3` (Multi-lingual / multi-aspect).
    3. `dsm5_qwen3_emb` (Native Qwen embedding).
  - All collections use the exact same chunk payload dataset, ensuring strict scientific parity.

### 3.3. Search Pipeline: Hybrid Retrieval & Cross-Encoder Reranking
- **Stage 1 — Candidate Generation (Hybrid Retrieval)**:
  - Retrieves top 20–30 candidates by fusing dense vector cosine similarity with lexical sparse matching (BM25 / Qdrant sparse vectors).
  - Addresses specific clinical acronyms, exact ICD codes (e.g. `300.02 (F41.1)`), and exact diagnostic terms that pure dense embeddings occasionally misrank.
- **Stage 2 — Candidate Reranking**:
  - Passes the top 20–30 candidates through a lightweight, local cross-encoder (`ms-marco-MiniLM-L-6-v2` or `FlashRank` / `bge-reranker-large`).
  - Distills candidates down to the top 5 most relevant chunks.
  - Reranker confidence filtering: if the highest-scoring candidate falls below a calibrated threshold, the query is marked as out-of-scope/unsupported.

### 3.4. Generation & Grounding Engine (`src/main.py`)
- **Generation Model**: Local `qwen3:8b` via Ollama with `num_ctx: 8192`.
- **Reasoning Mode Toggle**:
  - Supports testing generation with thinking enabled vs. thinking disabled (comparing latency, clinical structure, and accuracy).
  - Optional benchmark against a hosted reference model.
- **Strict Grounding & Citation Enforcement**:
  - System prompt enforces that every diagnostic statement cites its exact source chunk (e.g., `[DSM-5 p. 260 | Generalized Anxiety Disorder]`).
  - Output validator flags claims made without backing citations.
- **Clinical Safety & Crisis Guardrail**:
  - Immediate intercept for queries expressing self-harm or suicidal intent, providing official crisis helpline resources without attempting automated diagnosis.
  - Out-of-scope refusal: queries asking for pharmaceutical dosing schedules or non-DSM treatment protocols gracefully output reference boundaries.

---

## 4. Empirical Evaluation Framework (`eval/`)

### 4.1. Golden Benchmark Dataset (`eval/questions.jsonl`)
- **40 Curated Questions**:
  - **20 Lookup Questions**: Direct inquiries on core diagnostic criteria, duration minimums, and symptom thresholds.
  - **12 Differential Diagnosis Questions**: Multilateral symptom combinations comparing overlapping disorders.
  - **8 Out-Of-Scope Questions**: Drug dosages, non-DSM protocols, psychotherapy protocols, and state legal commitments.
- **Ground-Truth Keys**:
  - Keyed on `gold_disorders` (canonical names), `gold_sections`, and `gold_pages`.
  - Independent of chunk IDs or chunking versions.

### 4.2. Metric Suite & Logging (`results.csv`)
For every experiment, `eval/run_eval.py` computes:
- **Recall@5**: Fraction of queries where a gold chunk appears in the top 5.
- **Recall@10**: Fraction of queries where a gold chunk appears in the top 10.
- **MRR (Mean Reciprocal Rank)**: Position penalty for the first relevant chunk.
- **Type Breakdowns**: Discrete Recall@5 and MRR for Lookup vs. Differential questions.
- **Out-of-Scope Rejection Accuracy**: Fraction of non-DSM queries successfully filtered below the confidence threshold.

Every run appends a row with a unique `config_label` and timestamp to `results.csv`.

---

## 5. Development Roadmap & Milestones

| Phase | Title | Key Deliverables | Success Criteria |
| :---: | :--- | :--- | :--- |
| **Phase 1** | **Evaluation Baseline** | • Curated 40-question benchmark (`eval/questions.jsonl`)<br>• Automated eval harness (`eval/run_eval.py`)<br>• Baseline v0 logged to `results.csv` | Baseline established: In-scope Recall@5: 68.75%, MRR: 0.4857. |
| **Phase 2** | **Qdrant Migration & Multi-Embedder Benchmarks** | • Local Qdrant container via Docker<br>• Migration of chunk payloads into Qdrant<br>• Benchmark `bge-large`, `bge-m3`, `qwen3-embedding` | Identify winning embedding model based on Recall@5 and MRR. |
| **Phase 3** | **Hybrid Search & Reranking** | • BM25 sparse index integration in Qdrant<br>• FlashRank / BGE cross-encoder reranker (retrieve 20–30, rerank to 5)<br>• Confidence threshold calibration | Increase In-scope Recall@5 to $\ge 85\%$, MRR to $\ge 0.70$. |
| **Phase 4** | **Generator Eval & Guardrails** | • Benchmark `qwen3:8b` (Thinking On vs. Off vs. Hosted)<br>• Citation verification layer<br>• Crisis guardrail intercept & OOS refusal | Zero hallucinated criteria; 100% citation coverage for diagnostic assertions. |
| **Phase 5** | **Packaging & Showcase** | • Unified `docker-compose.yml`<br>• Professional GitHub README with benchmark progress table<br>• Architecture diagram & demo walkthrough video | One-click reproducibility with verifiable portfolio metrics. |

---

## 6. Current Baseline Metrics (v0)

| Config Label | Recall@5 | Recall@10 | MRR | Lookup R@5 | Diff R@5 | OOS Rejection |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `baseline_v0_pinecone_bge_large` | **68.75%** | **75.00%** | **0.4857** | 65.00% | 75.00% | 62.50% |

*Every subsequent architectural iteration will directly benchmark against this baseline table.*

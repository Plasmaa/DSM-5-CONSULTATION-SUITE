# DSM-5 AI Consultation Suite 🧠💻

A high-fidelity, hybrid Retrieval-Augmented Generation (RAG) system built over the **Diagnostic and Statistical Manual of Mental Disorders, Fifth Edition (DSM-5)**. The application features a senior "Chief of Psychiatry / Boss Psychologist" clinical persona and a premium glassmorphic dashboard interface for clinical inquiry support.

---

## 🌟 Key Features

* **Structure-Aware Document Chunking**: Custom state-machine parser ([`src/chunker.py`](/src/chunker.py)) that reads the PDF, preserves disorder hierarchies, extracts ICD codes, isolates diagnostic criteria from other subsections (like *Differential Diagnosis* or *Prevalence*), joins hyphenated line breaks, and sanitizes OCR anomalies.
* **Hybrid Vector Architecture**: 
  * **Pinecone Cloud**: Serves as a fast, high-performance vector index for similarity queries.
  * **Local SQLite Cache**: Stores full chunk texts and metadata locally. When Pinecone returns vector IDs, text is fetched instantly from the local database, minimizing cloud latency and saving bandwidth.
* **Deterministic ID Deduplication**: Generates unique MD5 hashes based on disorder names, section types, and page numbers. This prevents duplicate chunk uploads if the indexer is run multiple times.
* **GPU-Accelerated Local Inference**: Integrates with a local **Ollama** server using the RTX 5060 GPU to run:
  * `bge-large` for fast vector embeddings (indexed all 1318 chunks in **64 seconds**).
  * `qwen2.5:7b` (or `llama3.1:8b`) for structured generation.
* **"Chief of Psychiatry" Persona**: A system prompt designed to enforce clinical authority, precision, and strict grounding. If an answer cannot be found in the DSM-5 context, the model explicitly states it rather than hallucinating.
* **Interactive Citations Drawer**: Inline citations in the chat panel act as clickable badges (e.g. `[ADHD, Page 60]`). Clicking a badge scrolls to and highlights the matching full text source card in the reference sidebar.

---

## 📐 System Architecture

```
                    ┌────────────────────────┐
                    │       DSM-5.pdf        │
                    └───────────┬────────────┘
                                │ (PyMuPDF Chunker)
                                ▼
                    ┌────────────────────────┐
                    │  1,308 Unique Chunks   │
                    └─────┬────────────┬─────┘
                          │            │
      (Ollama Embeddings) │            │ (Metadata Insertion)
                          ▼            ▼
                 ┌───────────────┐ ┌───────────────┐
                 │   Pinecone    │ │ Local SQLite  │
                 │ dsm5-index v1 │ │ dsm5_cache.db │
                 └───────┬───────┘ └───────┬───────┘
                         │                 │
            (Vector IDs) │                 │ (Source Fetch)
                         ▼                 ▼
                    ┌────────────────────────┐
                    │    FastAPI Backend     │
                    └───────────▲────────────┘
                                │
        (Grounding Context)     │
        (System Prompt     )    │ (User Message History)
                                ▼
                    ┌────────────────────────┐
                    │     Local Ollama       │
                    │   (Qwen2.5:7b on GPU)  │
                    └───────────┬────────────┘
                                │
                                │ (SSE Tokens Stream)
                                ▼
                    ┌────────────────────────┐
                    │  Glassmorphic Chat UI  │
                    │      (Web Browser)     │
                    └────────────────────────┘
```

---

## 🛠️ Installation & Setup

### Prerequisites
1. **Python 3.12+**
2. **Ollama** (Download from [ollama.com](https://ollama.com))
3. **NVIDIA GPU** with CUDA support (Recommended)

### 1. Clone & Set Up Environment
```bash
# Clone the repository
git clone https://github.com/Plasmaa/DSM-5-CONSULTATION-SUITE.git
cd DSM-5-CONSULTATION-SUITE

# Create a virtual environment
python -m venv .venv
# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Activate virtual environment (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
PINECONE_API_KEY=your_pinecone_api_key_here
```

### 3. Set Up Ollama Models
Ensure Ollama is running, then pull the required models:
```bash
# Pull the LLM reasoning model
ollama pull qwen2.5:7b

# Pull the BGE-Large embedding model
ollama pull bge-large
```

### 4. Index the DSM-5 PDF
Place your copy of the `DSM-5.pdf` in the project root directory, then run the indexing pipeline:
```bash
python src/index.py
```
This script will parse the PDF, generate embeddings on the GPU, insert text into `dsm5_cache.db`, and upsert vectors to Pinecone.

---

## 🚀 Running the Application

Start the FastAPI backend:
```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 📁 File Structure

```
DSM-5-CONSULTATION-SUITE/
│
├── public/                 # Static Frontend SPA Assets
│   ├── index.html          # Glassmorphic Workspace Dashboard
│   ├── app.css             # Styling & Transitions
│   └── app.js              # Streaming Event Handler & Citation Bindings
│
├── src/                    # Backend API & Chunker Logic
│   ├── chunker.py          # Structure-Aware PDF Parser
│   ├── db.py               # Hybrid Pinecone/SQLite DB Manager
│   ├── index.py            # CLI Indexing Pipeline
│   └── main.py             # FastAPI App with SSE Streaming & System Prompt
│
├── requirements.txt        # Package Dependencies
├── .gitignore              # Confidentiality Filter (.env, *.pdf, *.db ignored)
└── README.md               # Documentation (This file)
```

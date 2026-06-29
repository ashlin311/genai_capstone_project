# Placement Preparation AI Assistant

An AI-powered assistant that helps students prepare for placements using **Retrieval-Augmented Generation (RAG)**. It retrieves relevant preparation materials from a curated knowledge base and generates personalized guidance using an LLM.

## Architecture

```
Knowledge Base (.txt files)
    → Chunking (500 chars, 100 overlap)
    → Embeddings (all-MiniLM-L6-v2)
    → FAISS Vector Database

User Query
    → Embedding
    → FAISS Similarity Search (top 5)
    → Retrieved Chunks + Query → Groq LLM (Llama 3.1)
    → Generated Answer
```

## Tech Stack

| Component    | Technology                              |
|-------------|----------------------------------------|
| Backend     | Python, FastAPI                         |
| LLM         | Groq API (Llama 3.1 8B Instant)        |
| Embeddings  | sentence-transformers/all-MiniLM-L6-v2 |
| Vector DB   | FAISS (faiss-cpu)                       |
| Framework   | LangChain                              |

## Project Structure

```
├── data/                  # Knowledge base documents
│   ├── tcs.txt            # TCS interview experiences
│   ├── aptitude.txt       # Aptitude preparation
│   ├── fastapi.txt        # FastAPI interview questions
│   ├── rag.txt            # RAG/LLM concepts
│   └── hr_questions.txt   # HR interview preparation
├── vectorstore/           # FAISS index (auto-generated)
├── ingest.py              # Document ingestion pipeline
├── retriever.py           # FAISS retrieval module
├── generator.py           # Groq LLM answer generation
├── api.py                 # FastAPI REST API
├── requirements.txt       # Python dependencies
├── .env                   # API keys (not committed)
└── README.md              # This file
```

## Setup & Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Get a free API key from [Groq Console](https://console.groq.com) and add it to `.env`:

```
GROQ_API_KEY=your_api_key_here
```

### 3. Build the Vector Store

```bash
python ingest.py
```

This loads documents from `data/`, chunks them, generates embeddings, and stores them in FAISS.

### 4. Start the API Server

```bash
uvicorn api:app --reload
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### Health Check

```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "vectorstore_loaded": true
}
```

### Ask a Question

```
POST /ask
```

Request:
```json
{
  "query": "TCS AI Intern Python FastAPI RAG interview preparation"
}
```

Response:
```json
{
  "answer": "Based on the preparation materials...",
  "sources": ["tcs.txt", "fastapi.txt", "rag.txt"]
}
```

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Module Details

| Module        | Responsibility                                          |
|--------------|--------------------------------------------------------|
| `ingest.py`  | Load documents → chunk → embed → store in FAISS        |
| `retriever.py`| Load FAISS index → similarity search → return top-k    |
| `generator.py`| Format prompt → call Groq LLM → return answer          |
| `api.py`     | FastAPI app with `/ask` and `/health` endpoints         |

## RAG Pipeline Justification

**Why RAG over fine-tuning?**
- No training compute required
- Easy to update knowledge base (just add new .txt files and re-run ingest)
- Reduces hallucinations by grounding responses in retrieved facts
- Cost-effective — uses free Groq API tier

**Why FAISS?**
- Fast similarity search
- Lightweight — runs on CPU
- Easy to persist and reload
- Good for prototyping and medium-scale applications

**Why Groq + Llama 3.1?**
- Free API tier available
- Extremely fast inference
- Good quality responses for structured Q&A tasks

## Team

Built as a GenAI capstone project.
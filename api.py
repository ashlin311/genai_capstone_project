"""
api.py — Unified FastAPI Application

Combines JD parsing and RAG-based placement preparation into a single API.

Endpoints:
    GET   /health     — Health check
    POST  /parse-jd   — Upload JD PDF → extract company, role, skills
    POST  /ask        — Ask a placement preparation question (text query)
    POST  /prepare    — Full pipeline: Upload JD PDF → parse → RAG → answer

Usage:
    python -m uvicorn api:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from retriever import load_vectorstore, retrieve
from generator import generate_answer
from pdf_parser import extract_text_from_pdf
from extractor import extract_jd_info, build_search_query


# --- Request/Response Models ---

class QueryRequest(BaseModel):
    """Request body for the /ask endpoint."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The placement preparation query",
        json_schema_extra={
            "example": "TCS AI Intern Python FastAPI RAG interview preparation"
        },
    )
    jd_context: str | None = Field(
        None,
        description="Optional active JD context summary or raw text to guide the query"
    )


class QueryResponse(BaseModel):
    """Response body for the /ask endpoint."""
    answer: str = Field(description="The generated answer from the AI assistant")
    sources: list[str] = Field(description="List of source documents used")


class JDResponse(BaseModel):
    """Response body for the /parse-jd endpoint."""
    company: str
    role: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]
    search_query: str
    raw_text: str = Field(description="The raw text extracted from the JD PDF")


class FullPipelineResponse(BaseModel):
    """Response body for the /prepare endpoint (full end-to-end pipeline)."""
    company: str
    role: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]
    search_query: str
    answer: str
    sources: list[str]
    raw_text: str = Field(description="The raw text extracted from the JD PDF")


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""
    status: str
    vectorstore_loaded: bool


# --- App State ---
app_state = {"vectorstore": None}


# --- Lifespan (Startup/Shutdown) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the FAISS vector store at startup."""
    vectorstore_dir = os.path.join(os.path.dirname(__file__), "vectorstore")

    try:
        print("[*] Loading FAISS vector store...")
        app_state["vectorstore"] = load_vectorstore(vectorstore_dir)
        print("[OK] Vector store loaded successfully!")
    except FileNotFoundError:
        print("[WARN] Vector store not found. Run 'python ingest.py' first.")
        app_state["vectorstore"] = None

    yield  # App is running

    app_state["vectorstore"] = None
    print("[*] Application shut down.")


# --- FastAPI App ---

app = FastAPI(
    title="Placement Preparation AI Assistant",
    description=(
        "An AI-powered assistant that helps students prepare for placements. "
        "Upload a Job Description PDF to get personalized preparation guidance "
        "powered by RAG (Retrieval-Augmented Generation)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from the 'static' directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", tags=["UI"])
async def serve_ui():
    """Serve the single-page web UI."""
    return FileResponse(os.path.join(static_dir, "index.html"))


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check if the API and vector store are operational."""
    return HealthResponse(
        status="healthy",
        vectorstore_loaded=app_state["vectorstore"] is not None,
    )


@app.post("/parse-jd", response_model=JDResponse, tags=["JD Parser"])
async def parse_jd(file: UploadFile = File(..., description="Job description PDF file")):
    """
    Upload a JD PDF and receive structured placement prep data.

    Steps:
    1. Validate the uploaded file is a PDF.
    2. Extract raw text using pypdf.
    3. Parse structured fields (company, role, skills, keywords).
    4. Build a search query for retrieving prep materials.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # Extract text from PDF
    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Parse JD structure
    try:
        jd_data = await extract_jd_info(raw_text, use_ai_fallback=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD extraction failed: {e}")

    # Build search query
    search_query = build_search_query(jd_data)

    return JDResponse(
        company=jd_data["company"],
        role=jd_data["role"],
        required_skills=jd_data["required_skills"],
        preferred_skills=jd_data["preferred_skills"],
        keywords=jd_data["keywords"],
        search_query=search_query,
        raw_text=raw_text,
    )


@app.post("/ask", response_model=QueryResponse, tags=["RAG"])
async def ask_question(request: QueryRequest):
    """
    Ask a placement preparation question.

    The system retrieves relevant preparation materials from the
    knowledge base and generates a personalized answer using an LLM.
    """
    if app_state["vectorstore"] is None:
        raise HTTPException(
            status_code=503,
            detail="Vector store is not loaded. Run 'python ingest.py' first.",
        )

    try:
        # Step 1: Retrieve relevant chunks from FAISS
        retrieved_chunks = retrieve(
            query=request.query,
            vectorstore=app_state["vectorstore"],
            k=5,
        )

        # Step 2: Generate answer using LLM (with optional active JD context)
        answer = generate_answer(
            query=request.query,
            retrieved_chunks=retrieved_chunks,
            jd_context=request.jd_context,
        )

        # Step 3: Extract unique source filenames
        sources = list(set(chunk["source"] for chunk in retrieved_chunks))

        return QueryResponse(answer=answer, sources=sources)

    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your query: {str(e)}",
        )


@app.post("/prepare", response_model=FullPipelineResponse, tags=["Full Pipeline"])
async def prepare_from_jd(
    file: UploadFile = File(..., description="Job description PDF file"),
    query: str | None = None,
):
    """
    Full end-to-end pipeline: Upload JD PDF → Parse → RAG → Answer.

    Optionally provide your own search query to override the auto-generated one.

    This is the main endpoint that combines both modules:
    1. Extract text from the uploaded JD PDF.
    2. Parse company, role, and skills from the JD.
    3. Build a search query (or use the provided custom query).
    4. Retrieve relevant preparation materials from FAISS.
    5. Generate a personalized preparation guide using the LLM.
    """
    if app_state["vectorstore"] is None:
        raise HTTPException(
            status_code=503,
            detail="Vector store is not loaded. Run 'python ingest.py' first.",
        )

    # --- JD Parsing ---

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        jd_data = await extract_jd_info(raw_text, use_ai_fallback=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD extraction failed: {e}")

    # Use custom query if provided, otherwise auto-generate from JD
    search_query = query.strip() if query and query.strip() else build_search_query(jd_data)

    # --- RAG Pipeline ---

    try:
        # Retrieve relevant chunks using the JD search query
        retrieved_chunks = retrieve(
            query=search_query,
            vectorstore=app_state["vectorstore"],
            k=5,
        )

        # Generate personalized preparation answer (passing full parsed text as JD context)
        answer = generate_answer(
            query=search_query,
            retrieved_chunks=retrieved_chunks,
            jd_context=raw_text,
        )

        sources = list(set(chunk["source"] for chunk in retrieved_chunks))

    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG pipeline failed: {str(e)}",
        )

    return FullPipelineResponse(
        company=jd_data["company"],
        role=jd_data["role"],
        required_skills=jd_data["required_skills"],
        preferred_skills=jd_data["preferred_skills"],
        keywords=jd_data["keywords"],
        search_query=search_query,
        answer=answer,
        sources=sources,
        raw_text=raw_text,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

"""
api.py — FastAPI Application

Exposes the RAG placement preparation assistant as a REST API.

Endpoints:
    GET  /health  — Health check
    POST /ask     — Ask a placement preparation question

Usage:
    uvicorn api:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from retriever import load_vectorstore, retrieve
from generator import generate_answer


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


class QueryResponse(BaseModel):
    """Response body for the /ask endpoint."""
    answer: str = Field(description="The generated answer from the AI assistant")
    sources: list[str] = Field(description="List of source documents used")


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""
    status: str
    vectorstore_loaded: bool


# --- App State ---
# Store the vector store in app state so it's loaded once at startup
app_state = {"vectorstore": None}


# --- Lifespan (Startup/Shutdown) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the FAISS vector store at startup."""
    vectorstore_dir = os.path.join(os.path.dirname(__file__), "vectorstore")

    try:
        print("🚀 Loading FAISS vector store...")
        app_state["vectorstore"] = load_vectorstore(vectorstore_dir)
        print("✅ Vector store loaded successfully!")
    except FileNotFoundError:
        print("⚠️  Vector store not found. Run 'python ingest.py' first.")
        print("   The /ask endpoint will not work until the vector store is built.")
        app_state["vectorstore"] = None

    yield  # App is running

    # Cleanup on shutdown
    app_state["vectorstore"] = None
    print("🛑 Application shut down.")


# --- FastAPI App ---

app = FastAPI(
    title="Placement Preparation AI Assistant",
    description=(
        "An AI-powered assistant that helps students prepare for placements. "
        "Uses RAG (Retrieval-Augmented Generation) to provide personalized "
        "preparation guidance based on curated placement materials."
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


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check if the API and vector store are operational."""
    return HealthResponse(
        status="healthy",
        vectorstore_loaded=app_state["vectorstore"] is not None,
    )


@app.post("/ask", response_model=QueryResponse, tags=["RAG"])
async def ask_question(request: QueryRequest):
    """
    Ask a placement preparation question.

    The system retrieves relevant preparation materials from the
    knowledge base and generates a personalized answer using an LLM.
    """
    # Check if vector store is loaded
    if app_state["vectorstore"] is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Vector store is not loaded. "
                "Run 'python ingest.py' first to build the knowledge base."
            ),
        )

    try:
        # Step 1: Retrieve relevant chunks from FAISS
        retrieved_chunks = retrieve(
            query=request.query,
            vectorstore=app_state["vectorstore"],
            k=5,
        )

        # Step 2: Generate answer using LLM
        answer = generate_answer(
            query=request.query,
            retrieved_chunks=retrieved_chunks,
        )

        # Step 3: Extract unique source filenames
        sources = list(set(chunk["source"] for chunk in retrieved_chunks))

        return QueryResponse(answer=answer, sources=sources)

    except ValueError as e:
        # Missing API key or configuration error
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your query: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

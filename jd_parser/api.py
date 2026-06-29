"""
api.py
------
FastAPI application exposing the JD parsing pipeline.

Endpoint:
  POST /parse-jd
    - Accepts a PDF file upload
    - Returns structured JSON with company, role, skills, and search query
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pdf_parser import extract_text_from_pdf
from extractor import extract_jd_info, build_search_query


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="JD Parser API",
    description="Upload a Job Description PDF to extract structured placement prep data.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class JDResponse(BaseModel):
    company: str
    role: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]
    search_query: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", summary="Health check")
def root():
    """Simple health-check endpoint."""
    return {"status": "ok", "message": "JD Parser API is running."}


@app.post("/parse-jd", response_model=JDResponse, summary="Parse a Job Description PDF")
async def parse_jd(file: UploadFile = File(..., description="Job description PDF file")):
    """
    Upload a JD PDF and receive structured placement prep data.

    Steps:
    1. Validate the uploaded file is a PDF.
    2. Extract raw text using pypdf.
    3. Parse structured fields (company, role, skills, keywords).
    4. Build a search query for retrieving prep materials.
    """

    # ---- Validate file type ----
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # ---- Read file bytes ----
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # ---- Extract text from PDF ----
    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF text extraction failed: {e}")

    # ---- Parse JD structure ----
    try:
        jd_data = await extract_jd_info(raw_text, use_ai_fallback=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD extraction failed: {e}")

    # ---- Build search query ----
    search_query = build_search_query(jd_data)

    return JDResponse(
        company=jd_data["company"],
        role=jd_data["role"],
        required_skills=jd_data["required_skills"],
        preferred_skills=jd_data["preferred_skills"],
        keywords=jd_data["keywords"],
        search_query=search_query,
    )


# ---------------------------------------------------------------------------
# Run directly: python api.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

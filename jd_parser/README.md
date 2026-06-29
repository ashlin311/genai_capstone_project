# JD Parser — Placement Preparation AI Module

A lightweight FastAPI backend that extracts structured data from Job Description PDFs for use in placement preparation systems.

---

## Project Structure

```
jd_parser/
├── pdf_parser.py      # PDF → raw text  (uses pypdf)
├── extractor.py       # raw text → structured fields + search query
├── api.py             # FastAPI app with POST /parse-jd endpoint
├── requirements.txt
└── README.md
```

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
python api.py
# or
uvicorn api:app --reload
```

Server runs at: http://localhost:8000
Interactive docs: http://localhost:8000/docs

---

## API Usage

### `POST /parse-jd`

Upload a JD PDF and receive structured JSON.

**curl example:**
```bash
curl -X POST http://localhost:8000/parse-jd \
  -F "file=@/path/to/job_description.pdf"
```

**Example response:**
```json
{
  "company": "TCS",
  "role": "AI Intern",
  "required_skills": ["Python", "FastAPI", "RAG", "Large Language Models"],
  "preferred_skills": [],
  "keywords": ["Problem Solving"],
  "search_query": "TCS AI Intern Python FastAPI RAG interview preparation"
}
```

---

## How It Works

### `pdf_parser.py`
Uses `pypdf.PdfReader` to iterate over PDF pages and concatenate extracted text.

### `extractor.py`
**Two-stage extraction pipeline:**

1. **Regex pass** — Fast, zero-cost parsing using section header detection and bullet/list scanning. Handles templated JDs reliably.
2. **AI fallback** — If company, role, or required skills are still missing, calls `claude-sonnet-4-6` via the Anthropic API for free-form NLP extraction.

Also scans for soft-skill / interview-prep keywords (problem solving, communication, leadership, etc.) and builds the final search query string.

### `api.py`
FastAPI app with:
- File validation (must be `.pdf`)
- Proper error handling at each stage
- Clean Pydantic response model

---

## JD Format Tips

The regex parser works best when the PDF follows this structure:

```
Company: <name>
Role: <title>

Requirements:
* Skill 1
* Skill 2

Preferred Skills:
* Nice-to-have skill
```

For unstructured PDFs (paragraph-form descriptions), the AI fallback handles extraction automatically.

---

## Next Steps (extending this module)

- Connect `search_query` to a vector database (FAISS / Pinecone) to retrieve prep materials
- Add support for DOCX job descriptions
- Cache results by PDF hash to avoid re-processing
- Add a `/batch-parse` endpoint for multiple JDs

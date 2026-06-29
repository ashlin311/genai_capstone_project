"""
extractor.py
------------
Parses raw JD text into structured fields and builds a search query.

Strategy:
  - Use regex + keyword matching for a fast, dependency-free approach.
  - Fall back to Claude AI (via Anthropic API) for richer extraction when
    the text doesn't follow a predictable format.
"""

import re
import json
from typing import TypedDict


# ---------------------------------------------------------------------------
# Type hint for the structured JD output
# ---------------------------------------------------------------------------

class JDData(TypedDict):
    company: str
    role: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]


# ---------------------------------------------------------------------------
# Common interview-prep keywords to look out for
# ---------------------------------------------------------------------------

INTERVIEW_KEYWORDS = [
    "problem solving", "communication", "teamwork", "leadership",
    "analytical", "critical thinking", "time management", "adaptability",
    "collaboration", "attention to detail", "self-motivated", "ownership",
    "agile", "scrum", "mentorship", "interpersonal",
]


# ---------------------------------------------------------------------------
# Regex-based extractor (works well for structured / templated JDs)
# ---------------------------------------------------------------------------

def _extract_with_regex(text: str) -> JDData:
    """
    Attempt to pull fields from text using common JD patterns.
    Returns a JDData dict (fields may be empty strings / empty lists).
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # ---- Company ----
    company = ""
    for line in lines:
        m = re.search(r"(?i)company\s*[:\-]\s*(.+)", line)
        if m:
            company = m.group(1).strip()
            break

    # ---- Role / Title ----
    role = ""
    role_patterns = [
        r"(?i)(?:role|job\s*title|position|title)\s*[:\-]\s*(.+)",
        r"(?i)we are hiring\s+(?:a|an)?\s*(.+)",
        r"(?i)hiring\s+(?:for\s+)?(?:a|an)?\s*(.+)",
    ]
    for line in lines:
        for pat in role_patterns:
            m = re.search(pat, line)
            if m:
                role = m.group(1).strip()
                break
        if role:
            break

    # ---- Skills sections ----
    required_skills: list[str] = []
    preferred_skills: list[str] = []

    # Identify section boundaries
    REQUIRED_HEADERS = re.compile(
        r"(?i)^(requirements?|required\s+skills?|must.have|technical\s+skills?|qualifications?)\s*[:\-]?\s*$"
    )
    PREFERRED_HEADERS = re.compile(
        r"(?i)^(preferred\s+skills?|nice.to.have|bonus|good\s+to\s+have|plus)\s*[:\-]?\s*$"
    )
    # Inline patterns like "Requirements: Python, FastAPI"
    INLINE_REQUIRED = re.compile(
        r"(?i)(?:requirements?|required\s+skills?|must.have|technical\s+skills?)\s*[:\-]\s*(.+)"
    )
    INLINE_PREFERRED = re.compile(
        r"(?i)(?:preferred\s+skills?|nice.to.have|bonus)\s*[:\-]\s*(.+)"
    )

    current_section = None  # "required" | "preferred" | None

    for line in lines:
        # Check section headers (standalone lines)
        if REQUIRED_HEADERS.match(line):
            current_section = "required"
            continue
        if PREFERRED_HEADERS.match(line):
            current_section = "preferred"
            continue

        # Check inline declarations
        m_req = INLINE_REQUIRED.match(line)
        if m_req:
            skills = _split_skills(m_req.group(1))
            required_skills.extend(skills)
            current_section = "required"
            continue

        m_pref = INLINE_PREFERRED.match(line)
        if m_pref:
            skills = _split_skills(m_pref.group(1))
            preferred_skills.extend(skills)
            current_section = "preferred"
            continue

        # Bullet / list item inside a section
        bullet_match = re.match(r"^[\*\-\•\◦\✓\>]\s+(.+)", line)
        numbered_match = re.match(r"^\d+[\.\)]\s+(.+)", line)
        item_text = None
        if bullet_match:
            item_text = bullet_match.group(1).strip()
        elif numbered_match:
            item_text = numbered_match.group(1).strip()

        if item_text and current_section == "required":
            required_skills.append(item_text)
        elif item_text and current_section == "preferred":
            preferred_skills.append(item_text)

    # ---- Interview-prep keywords (scan full text) ----
    text_lower = text.lower()
    found_keywords = [kw for kw in INTERVIEW_KEYWORDS if kw in text_lower]

    # Remove any keywords already captured in skills lists
    all_skills_lower = {s.lower() for s in required_skills + preferred_skills}
    keywords = [kw for kw in found_keywords if kw not in all_skills_lower]

    return JDData(
        company=company,
        role=role,
        required_skills=_deduplicate(required_skills),
        preferred_skills=_deduplicate(preferred_skills),
        keywords=_deduplicate(keywords),
    )


def _split_skills(text: str) -> list[str]:
    """Split a comma/semicolon separated skill string into a list."""
    parts = re.split(r"[,;/]", text)
    return [p.strip() for p in parts if p.strip()]


def _deduplicate(items: list[str]) -> list[str]:
    """Return list with duplicates removed, preserving order."""
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# AI-powered extractor (fallback for unstructured JDs)
# ---------------------------------------------------------------------------

async def _extract_with_ai(text: str) -> JDData:
    """
    Use Claude (via the Anthropic API) to extract structured data from
    free-form JD text. Called only when regex extraction is incomplete.
    """
    import httpx  # lightweight async HTTP client

    prompt = f"""You are a job description parser. Extract the following fields from the JD text below.

Return ONLY a valid JSON object with these keys:
- "company": string (company name, empty string if not found)
- "role": string (job title / role, empty string if not found)
- "required_skills": array of strings
- "preferred_skills": array of strings (empty array if none)
- "keywords": array of strings (soft skills or interview prep keywords)

Do NOT include any explanation or markdown. Return raw JSON only.

JD TEXT:
\"\"\"
{text}
\"\"\"
"""

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

    raw = data["content"][0]["text"].strip()
    # Strip possible markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    parsed = json.loads(raw)
    return JDData(
        company=parsed.get("company", ""),
        role=parsed.get("role", ""),
        required_skills=parsed.get("required_skills", []),
        preferred_skills=parsed.get("preferred_skills", []),
        keywords=parsed.get("keywords", []),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def extract_jd_info(text: str, use_ai_fallback: bool = True) -> JDData:
    """
    Extract structured JD information from raw text.

    First tries fast regex-based extraction. If key fields (company, role,
    required_skills) are still missing and `use_ai_fallback` is True, it
    delegates to the Claude AI model for a second attempt.

    Args:
        text: Raw text extracted from the PDF.
        use_ai_fallback: Whether to call the AI API when regex is insufficient.

    Returns:
        JDData TypedDict with all structured fields.
    """
    result = _extract_with_regex(text)

    # Check if extraction was sufficient
    missing_critical = not result["company"] or not result["role"] or not result["required_skills"]

    if missing_critical and use_ai_fallback:
        try:
            ai_result = await _extract_with_ai(text)
            # Merge: prefer AI values for missing fields, keep regex values otherwise
            result["company"] = result["company"] or ai_result["company"]
            result["role"] = result["role"] or ai_result["role"]
            result["required_skills"] = result["required_skills"] or ai_result["required_skills"]
            result["preferred_skills"] = result["preferred_skills"] or ai_result["preferred_skills"]
            result["keywords"] = _deduplicate(result["keywords"] + ai_result["keywords"])
        except Exception as e:
            # AI fallback failed — return whatever regex found
            print(f"[extractor] AI fallback failed: {e}")

    return result


def build_search_query(jd: JDData) -> str:
    """
    Compose a search query string from the structured JD data.

    Format:
      "{company} {role} {skill1} {skill2} ... interview preparation"

    Args:
        jd: Structured JD data dictionary.

    Returns:
        A search-engine-friendly query string.
    """
    parts: list[str] = []

    if jd["company"]:
        parts.append(jd["company"])
    if jd["role"]:
        parts.append(jd["role"])

    # Include up to 5 required skills to keep the query focused
    for skill in jd["required_skills"][:5]:
        parts.append(skill)

    parts.append("interview preparation")

    return " ".join(parts)

"""
generator.py — Answer Generation Module

Takes retrieved context chunks and a user query, then generates
a placement preparation answer using the Groq LLM API.
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.1-8b-instant"
TEMPERATURE = 0.3

# --- Prompt Template ---
PLACEMENT_PROMPT = ChatPromptTemplate.from_template(
    """You are a placement preparation assistant.

{jd_context_block}

Answer only using the retrieved context. If the user asks specifically about the active Job Description (JD) details provided above, you can also use those details to answer.
If relevant context is not found in the documents or the active JD, say:
"I could not find enough relevant preparation material."

Provide a well-structured, helpful answer with:
- Clear headings and bullet points
- Specific examples when available
- Actionable preparation tips

Context:
{context}

Question:
{query}

Answer:"""
)


def get_llm():
    """Initialize the Groq LLM client."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not found. Create a .env file with:\n"
            "GROQ_API_KEY=your_api_key_here\n"
            "Get a free key at: https://console.groq.com"
        )

    llm = ChatGroq(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        groq_api_key=GROQ_API_KEY,
    )
    return llm


def generate_answer(query: str, retrieved_chunks: list, jd_context: str = None) -> str:
    """
    Generate an answer using the LLM with retrieved context and optional JD context.

    Args:
        query: The user's question.
        retrieved_chunks: List of dicts with 'content' and 'source' keys.
        jd_context: Optional active JD text/details context.

    Returns:
        The generated answer string.
    """
    # Combine retrieved chunks into a single context string
    context = "\n\n---\n\n".join(
        f"[Source: {chunk['source']}]\n{chunk['content']}"
        for chunk in retrieved_chunks
    )

    # Format the JD context block if present
    jd_context_block = ""
    if jd_context and jd_context.strip():
        jd_context_block = f"--- ACTIVE JOB DESCRIPTION CONTEXT ---\n{jd_context.strip()}\n--------------------------------------"

    # Create the prompt and generate the answer
    llm = get_llm()
    chain = PLACEMENT_PROMPT | llm

    response = chain.invoke({
        "context": context,
        "query": query,
        "jd_context_block": jd_context_block,
    })

    return response.content


if __name__ == "__main__":
    # Quick test with sample chunks
    sample_chunks = [
        {
            "content": "TCS NQT consists of Numerical Ability, Verbal Ability, Reasoning, and Coding sections.",
            "source": "tcs.txt",
        },
        {
            "content": "FastAPI is a modern Python web framework with automatic validation and async support.",
            "source": "fastapi.txt",
        },
    ]

    test_query = "How should I prepare for a TCS interview for an AI role?"
    print(f"🔍 Query: {test_query}\n")

    answer = generate_answer(test_query, sample_chunks)
    print(f"💡 Answer:\n{answer}")

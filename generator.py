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

Answer only using the retrieved context below.
If relevant context is not found, say:
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


def generate_answer(query: str, retrieved_chunks: list) -> str:
    """
    Generate an answer using the LLM with retrieved context.

    Args:
        query: The user's question.
        retrieved_chunks: List of dicts with 'content' and 'source' keys.

    Returns:
        The generated answer string.
    """
    # Combine retrieved chunks into a single context string
    context = "\n\n---\n\n".join(
        f"[Source: {chunk['source']}]\n{chunk['content']}"
        for chunk in retrieved_chunks
    )

    # If no context was retrieved, return a default message
    if not context.strip():
        return "I could not find enough relevant preparation material."

    # Create the prompt and generate the answer
    llm = get_llm()
    chain = PLACEMENT_PROMPT | llm

    response = chain.invoke({
        "context": context,
        "query": query,
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

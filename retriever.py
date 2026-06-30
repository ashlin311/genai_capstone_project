"""
retriever.py — Document Retrieval Module

Loads the persisted FAISS vector store and retrieves the most
relevant document chunks for a given query.
"""

import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# --- Configuration ---
VECTORSTORE_DIR = os.path.join(os.path.dirname(__file__), "vectorstore")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5


def load_vectorstore(vectorstore_dir: str = VECTORSTORE_DIR):
    """Load the FAISS vector store from disk."""
    if not os.path.exists(vectorstore_dir):
        raise FileNotFoundError(
            f"Vector store not found at '{vectorstore_dir}'. "
            "Run 'python ingest.py' first to build the vector store."
        )

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )

    vectorstore = FAISS.load_local(
        vectorstore_dir,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return vectorstore


def retrieve(query: str, vectorstore=None, k: int = TOP_K):
    """
    Retrieve the top-k most relevant chunks for a given query.

    Args:
        query: The search query string.
        vectorstore: Pre-loaded FAISS vector store (optional).
        k: Number of chunks to retrieve.

    Returns:
        List of dicts with 'content' and 'source' keys.
    """
    if vectorstore is None:
        vectorstore = load_vectorstore()

    # Perform similarity search
    results = vectorstore.similarity_search_with_score(query, k=k)

    retrieved_chunks = []
    # Lower L2 score is better. Filter out items with score > 1.15 to prevent noise.
    SCORE_THRESHOLD = 1.15

    for doc, score in results:
        score_val = float(score)
        if score_val <= SCORE_THRESHOLD:
            # Extract the source filename from metadata
            source = os.path.basename(doc.metadata.get("source", "unknown"))
            retrieved_chunks.append({
                "content": doc.page_content,
                "source": source,
                "score": round(score_val, 4),
            })

    return retrieved_chunks


if __name__ == "__main__":
    # Quick test
    test_query = "TCS AI Intern Python FastAPI RAG interview preparation"
    print(f"🔍 Query: {test_query}\n")

    chunks = retrieve(test_query)
    for i, chunk in enumerate(chunks, 1):
        print(f"--- Chunk {i} (source: {chunk['source']}, score: {chunk['score']}) ---")
        print(chunk["content"][:200] + "...")
        print()

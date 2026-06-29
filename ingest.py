"""
ingest.py — Document Ingestion Module

Loads placement preparation documents from the data/ directory,
splits them into chunks, generates embeddings, and stores them
in a FAISS vector database.

Usage:
    python ingest.py
"""

import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VECTORSTORE_DIR = os.path.join(os.path.dirname(__file__), "vectorstore")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def load_documents(data_dir: str):
    """Load all .txt files from the data directory."""
    print(f"📂 Loading documents from: {data_dir}")

    loader = DirectoryLoader(
        data_dir,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    documents = loader.load()
    print(f"✅ Loaded {len(documents)} document(s)")
    return documents


def split_documents(documents, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
    """Split documents into smaller chunks for embedding."""
    print(f"✂️  Splitting documents (chunk_size={chunk_size}, overlap={chunk_overlap})")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"✅ Created {len(chunks)} chunks")
    return chunks


def create_embeddings():
    """Initialize the HuggingFace embedding model."""
    print(f"🧠 Loading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )
    print("✅ Embedding model loaded")
    return embeddings


def build_vectorstore(chunks, embeddings, output_dir: str = VECTORSTORE_DIR):
    """Create a FAISS vector store from document chunks and save to disk."""
    print("📦 Building FAISS vector store...")

    vectorstore = FAISS.from_documents(chunks, embeddings)

    # Save to disk for later use
    os.makedirs(output_dir, exist_ok=True)
    vectorstore.save_local(output_dir)
    print(f"✅ Vector store saved to: {output_dir}")
    return vectorstore


def run_ingestion():
    """Run the full ingestion pipeline."""
    print("=" * 60)
    print("🚀 Starting Document Ingestion Pipeline")
    print("=" * 60)

    # Step 1: Load documents
    documents = load_documents(DATA_DIR)

    # Step 2: Split into chunks
    chunks = split_documents(documents)

    # Step 3: Create embeddings model
    embeddings = create_embeddings()

    # Step 4: Build and save FAISS vector store
    vectorstore = build_vectorstore(chunks, embeddings)

    print("=" * 60)
    print("✅ Ingestion pipeline completed successfully!")
    print(f"   Documents: {len(documents)}")
    print(f"   Chunks:    {len(chunks)}")
    print(f"   Stored in: {VECTORSTORE_DIR}")
    print("=" * 60)

    return vectorstore


if __name__ == "__main__":
    run_ingestion()

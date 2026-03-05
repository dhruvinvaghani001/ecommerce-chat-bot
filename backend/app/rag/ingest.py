import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from app.config import settings

DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "documents")


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name="ecom_chat_docs",
        embedding_function=get_embeddings(),
        persist_directory=settings.CHROMA_PERSIST_DIR,
    )


def ingest_documents() -> int:
    """Load all PDFs and text files from the documents directory into ChromaDB."""
    if not os.path.exists(DOCUMENTS_DIR):
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        print(f"Created documents directory at {DOCUMENTS_DIR}")
        return 0

    all_docs = []

    for filename in os.listdir(DOCUMENTS_DIR):
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(filepath)
            all_docs.extend(loader.load())
        elif filename.endswith(".txt") or filename.endswith(".md"):
            loader = TextLoader(filepath, encoding="utf-8")
            all_docs.extend(loader.load())

    if not all_docs:
        print("No documents found to ingest.")
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)

    vector_store = get_vector_store()
    vector_store.add_documents(chunks)

    print(f"Ingested {len(chunks)} chunks from {len(all_docs)} document pages.")
    return len(chunks)


if __name__ == "__main__":
    ingest_documents()

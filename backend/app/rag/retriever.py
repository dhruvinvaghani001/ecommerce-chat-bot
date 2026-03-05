from .ingest import get_vector_store


def search_documents(query: str, k: int = 4) -> list[dict]:
    """Search the vector store for relevant document chunks."""
    store = get_vector_store()

    try:
        results = store.similarity_search_with_score(query, k=k)
    except Exception:
        return []

    docs = []
    for doc, score in results:
        docs.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page", 0),
                "score": round(float(score), 4),
            }
        )
    return docs

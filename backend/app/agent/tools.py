import json
from langchain_core.tools import tool
from app.products.service import (
    search_products as _search_products,
    get_product_by_slug,
    get_similar_products as _get_similar,
)
from app.rag.retriever import search_documents as _search_docs


@tool
def search_products(
    query: str = "",
    product_type: str = "",
    location: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
) -> str:
    """Search for properties/products with optional filters.

    Args:
        query: Free-text search query (e.g. "luxury villa", "2 bedroom")
        product_type: Filter by type - "villa", "apartment", "penthouse", "townhouse"
        location: Filter by location (e.g. "Dubai Marina", "JVC", "Downtown")
        min_price: Minimum price filter
        max_price: Maximum price filter

    Returns:
        JSON string with product listing data including items and pagination.
    """
    result = _search_products(
        query=query,
        product_type=product_type,
        location=location,
        min_price=min_price,
        max_price=max_price,
    )
    return json.dumps({"component_type": "card-list", "data": result})


@tool
def get_product_details(slug: str) -> str:
    """Get detailed information about a specific product/property by its slug identifier.

    Args:
        slug: The product slug (URL-friendly identifier like "serge33-luxury-villa")

    Returns:
        JSON string with detailed product information.
    """
    result = get_product_by_slug(slug)
    if result is None:
        return json.dumps({"error": "Product not found", "slug": slug})
    return json.dumps({"component_type": "card-detail", "data": result})


@tool
def get_similar_products(product_type: str) -> str:
    """Find similar products based on property type.

    Args:
        product_type: The type of property to find similar items for (e.g. "villa", "apartment")

    Returns:
        JSON string with similar product listings.
    """
    ptype = product_type.replace("type:", "").strip()
    result = _get_similar(ptype)
    return json.dumps({"component_type": "card-list", "data": result})


@tool
def search_documents(query: str) -> str:
    """Search through company documents, policies, FAQs, and knowledge base.

    Use this when the user asks about policies, terms and conditions,
    company information, or any question that might be answered by documents.

    Args:
        query: The search query about policies, terms, or company info.

    Returns:
        JSON string with relevant document excerpts.
    """
    results = _search_docs(query, k=3)
    if not results:
        return json.dumps(
            {"message": "No relevant documents found for this query."}
        )
    context = "\n\n---\n\n".join(
        [
            f"Source: {r['source']} (page {r['page']})\n{r['content']}"
            for r in results
        ]
    )
    return json.dumps({"context": context, "sources": [r["source"] for r in results]})


ALL_TOOLS = [search_products, get_product_details, get_similar_products, search_documents]

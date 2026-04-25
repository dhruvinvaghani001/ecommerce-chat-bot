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
    name: str = "",
    price: str = "",
    category: str = "",
    climate: str = "",
    collar: str = "",
    color: str = "",
    eco_collection: str = "",
    erin_recommends: str = "",
    features_bags: str = "",
    format: str = "",
    gender: str = "",
    material: str = "",
    pattern: str = "",
    performance_fabric: str = "",
    sale: str = "",
    size: str = "",
    sleeve: str = "",
    strap_bags: str = "",
    style_bags: str = "",
    style_bottom: str = "",
    style_general: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = 1,
) -> str:
    """Search the Magento catalog with search text, price, and attribute filters.

    Args:
        query: Free-text search query
        name: Product name filter
        price: Price text such as "under 100", "50-100", or "above 75"
        category: Category filter
        climate: Climate filter
        collar: Collar filter
        color: Color filter
        eco_collection: Eco collection filter
        erin_recommends: Erin recommends filter
        features_bags: Bag features filter
        format: Format filter
        gender: Gender filter
        material: Material filter
        pattern: Pattern filter
        performance_fabric: Performance fabric filter
        sale: Sale filter
        size: Size filter
        sleeve: Sleeve filter
        strap_bags: Bag strap filter
        style_bags: Bag style filter
        style_bottom: Bottom style filter
        style_general: General style filter
        min_price: Minimum price filter override
        max_price: Maximum price filter override
        page: Results page number for pagination

    Returns:
        JSON string with product listing data including items and pagination.
    """
    result = _search_products(
        query=query,
        name=name,
        price=price,
        category=category,
        climate=climate,
        collar=collar,
        color=color,
        eco_collection=eco_collection,
        erin_recommends=erin_recommends,
        features_bags=features_bags,
        format=format,
        gender=gender,
        material=material,
        pattern=pattern,
        performance_fabric=performance_fabric,
        sale=sale,
        size=size,
        sleeve=sleeve,
        strap_bags=strap_bags,
        style_bags=style_bags,
        style_bottom=style_bottom,
        style_general=style_general,
        min_price=min_price,
        max_price=max_price,
        page=page,
    )
    return json.dumps({"component_type": "card-list", "data": result})


@tool
def get_product_details(slug: str) -> str:
    """Get detailed information about a specific product by its Magento url_key.

    Args:
        slug: The Magento product url_key (for example "erika-running-short")

    Returns:
        JSON string with detailed product information.
    """
    result = get_product_by_slug(slug)
    if result is None:
        return json.dumps({"error": "Product not found", "slug": slug})
    return json.dumps({"component_type": "card-detail", "data": result})


@tool
def get_similar_products(product_type: str) -> str:
    """Find related products using a keyword fallback search.

    Args:
        product_type: Keyword to search related products with.

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

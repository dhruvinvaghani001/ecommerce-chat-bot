import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool, tool
from pydantic import Field, create_model

from app.products.service import (
    get_product_by_slug,
    get_similar_products as _get_similar,
    search_products as _search_products,
)
from app.rag.retriever import search_documents as _search_docs

logger = logging.getLogger(__name__)

PRODUCT_FETCH_ERROR_MESSAGE = "Failed to fetch products currently."
PRODUCT_DETAILS_ERROR_MESSAGE = "Failed to fetch product details currently."
SIMILAR_PRODUCTS_ERROR_MESSAGE = "Failed to fetch similar products currently."


def _first_focus_filter(search_meta: dict[str, Any]) -> tuple[str, str] | None:
    ignored_keys = {
        "query",
        "name",
        "price",
        "minPrice",
        "maxPrice",
        "page",
        "pageSize",
        "unsupportedAttributes",
    }
    for key, value in search_meta.items():
        if key in ignored_keys:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return key, text
    return None


def _build_product_result_hint(result: dict[str, Any]) -> str:
    search_meta = result.get("searchMeta", {}) or {}
    name = str(search_meta.get("name", "")).strip()
    if name:
        focus = f"products for {name}"
    else:
        query = str(search_meta.get("query", "")).strip()
        filter_match = _first_focus_filter(search_meta)
        if filter_match:
            key, value = filter_match
            focus = f"products for {key.replace('_', ' ')} {value}"
        elif query:
            focus = f"products for {query}"
        else:
            focus = "products"

    return (
        "Reply with exactly one short sentence only. "
        f"Summarize the result focus as '{focus}'. "
        "Do not list product names, links, prices, descriptions, or bullets because the cards already show them."
    )


def _normalize_search_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {}

    attributes = context.get("attributes")
    normalized_attributes = (
        {
            str(key).strip(): value
            for key, value in attributes.items()
            if str(key).strip() and value not in (None, "")
        }
        if isinstance(attributes, dict)
        else {}
    )

    normalized: dict[str, Any] = {}
    for key in ("query", "name", "price", "minPrice", "maxPrice", "page", "pageSize", "summary"):
        value = context.get(key)
        if value not in (None, ""):
            normalized[key] = value
    if normalized_attributes:
        normalized["attributes"] = normalized_attributes
    return normalized


def _search_summary(context: dict[str, Any]) -> str:
    attributes = context.get("attributes", {}) if isinstance(context, dict) else {}
    category = str(attributes.get("category", "")).strip() if isinstance(attributes, dict) else ""
    if category:
        return f"category {category}"

    name = str(context.get("name", "")).strip()
    if name:
        return f"name {name}"

    query = str(context.get("query", "")).strip()
    if query:
        return f"search {query}"

    focus = _first_focus_filter(
        {
            **(attributes if isinstance(attributes, dict) else {}),
            "minPrice": context.get("minPrice"),
            "maxPrice": context.get("maxPrice"),
        }
    )
    if focus:
        key, value = focus
        return f"{key.replace('_', ' ')} {value}"
    return "current results"


def _refinement_summary(context: dict[str, Any]) -> str:
    attributes = context.get("attributes", {}) if isinstance(context, dict) else {}
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            text = str(value).strip()
            if text:
                return f"{key.replace('_', ' ')} {text}"

    name = str(context.get("name", "")).strip()
    if name:
        return f"name {name}"

    query = str(context.get("query", "")).strip()
    if query:
        return query

    min_price = context.get("minPrice")
    max_price = context.get("maxPrice")
    if min_price is not None and max_price is not None:
        return f"price {min_price:g}-{max_price:g}"
    if min_price is not None:
        return f"price above {min_price:g}"
    if max_price is not None:
        return f"price below {max_price:g}"

    return ""


def _build_search_products_args_schema():
    field_definitions: dict[str, tuple[Any, Any]] = {
        "query": (
            str,
            Field(default="", description="Free-text search query."),
        ),
        "user_request": (
            str,
            Field(
                default="",
                description="The full raw user shopping request for backend filter resolution.",
            ),
        ),
        "name": (
            str,
            Field(default="", description="Product name filter."),
        ),
        "price": (
            str,
            Field(
                default="",
                description='Price text such as "under 100", "50-100", or "above 75".',
            ),
        ),
        "attributes": (
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Generic storefront attribute filters from Magento aggregations, "
                    'for example {"category": "Snacks", "brand": "Tong Garden"}.'
                ),
            ),
        ),
        "min_price": (
            float | None,
            Field(default=None, description="Minimum price filter override."),
        ),
        "max_price": (
            float | None,
            Field(default=None, description="Maximum price filter override."),
        ),
        "page": (
            int,
            Field(default=1, description="Results page number for pagination."),
        ),
    }

    return create_model("SearchProductsInput", **field_definitions)


SEARCH_PRODUCTS_ARGS_SCHEMA = _build_search_products_args_schema()


def _search_products_tool_impl(**kwargs: Any) -> str:
    try:
        result = _search_products(**kwargs)
    except Exception:
        logger.exception("search_products failed")
        return json.dumps({"message": PRODUCT_FETCH_ERROR_MESSAGE})
    if result.get("validationError"):
        return json.dumps(
            {
                "message": result["validationError"]["message"],
                "validationError": result["validationError"],
                "searchMeta": result.get("searchMeta", {}),
            }
        )
    return json.dumps(
        {
            "component_type": "card-list",
            "data": result,
            "search_context": result.get("searchMeta", {}),
            "assistant_hint": _build_product_result_hint(result),
        }
    )


search_products = StructuredTool.from_function(
    func=_search_products_tool_impl,
    name="search_products",
    description=(
        "Search the Magento catalog with free-text search, price filters, pagination, "
        "and storefront attribute filters. Use the `attributes` object for catalog "
        "filters exposed by Magento aggregations, such as category, brand, size, or color. "
        "Always pass the full raw shopping request in `user_request`."
    ),
    args_schema=SEARCH_PRODUCTS_ARGS_SCHEMA,
    infer_schema=False,
)


def _build_prepare_search_confirmation_args_schema():
    field_definitions: dict[str, tuple[Any, Any]] = {
        "user_request": (
            str,
            Field(
                ...,
                description="The user's latest ambiguous follow-up request, for example 'size M'.",
            ),
        ),
        "current_search": (
            dict[str, Any] | None,
            Field(
                default=None,
                description="The active search context that may be kept, including query, price, and attributes.",
            ),
        ),
        "proposed_search": (
            dict[str, Any] | None,
            Field(
                default=None,
                description="Only the newly requested refinement fields inferred from the latest message.",
            ),
        ),
    }
    return create_model("PrepareSearchConfirmationInput", **field_definitions)


PREPARE_SEARCH_CONFIRMATION_ARGS_SCHEMA = _build_prepare_search_confirmation_args_schema()


def _prepare_search_confirmation_impl(**kwargs: Any) -> str:
    current_search = _normalize_search_context(kwargs.get("current_search"))
    proposed_search = _normalize_search_context(kwargs.get("proposed_search"))
    user_request = str(kwargs.get("user_request", "")).strip()
    summary = _search_summary(current_search)
    refinement = _refinement_summary(proposed_search)

    return json.dumps(
        {
            "internal_state": {
                "type": "pending_search_confirmation",
                "data": {
                    "userRequest": user_request,
                    "currentSearch": current_search,
                    "proposedSearch": proposed_search,
                },
            },
            "assistant_hint": (
                "Ask exactly one short confirmation question only. "
                "Use plain language and no explanation. "
                "Do not say 'Would you like' or 'current search context'. "
                f"Current focus: {summary}. "
                f"New refinement: {refinement or user_request}. "
                "Preferred style examples: "
                f"'Apply {refinement or user_request} to the same {summary}, or switch category?' "
                f"or 'For the same {summary}, or a different category?'"
            ),
        }
    )


prepare_search_confirmation = StructuredTool.from_function(
    func=_prepare_search_confirmation_impl,
    name="prepare_search_confirmation",
    description=(
        "Prepare an LLM-led confirmation step for an ambiguous short follow-up filter. "
        "Use this instead of searching immediately when the user might mean either "
        "the current results or a fresh category/search."
    ),
    args_schema=PREPARE_SEARCH_CONFIRMATION_ARGS_SCHEMA,
    infer_schema=False,
)


@tool
def get_product_details(slug: str) -> str:
    """Get detailed information about a specific product by its Magento url_key.

    Args:
        slug: The Magento product url_key (for example "erika-running-short")

    Returns:
        JSON string with detailed product information.
    """
    try:
        result = get_product_by_slug(slug)
    except Exception:
        logger.exception("get_product_details failed for slug=%r", slug)
        return json.dumps({"message": PRODUCT_DETAILS_ERROR_MESSAGE})
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
    try:
        result = _get_similar(ptype)
    except Exception:
        logger.exception("get_similar_products failed for product_type=%r", product_type)
        return json.dumps({"message": SIMILAR_PRODUCTS_ERROR_MESSAGE})
    return json.dumps(
        {
            "component_type": "card-list",
            "data": result,
            "assistant_hint": (
                "Reply with exactly one short sentence only. "
                f"Summarize the result focus as 'similar products for {ptype or 'this item'}'. "
                "Do not list product names, links, prices, descriptions, or bullets because the cards already show them."
            ),
        }
    )


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


ALL_TOOLS = [
    search_products,
    prepare_search_confirmation,
    get_product_details,
    get_similar_products,
    search_documents,
]

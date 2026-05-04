from __future__ import annotations

import json
import logging
import re
import time
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings

logger = logging.getLogger(__name__)

FILTER_ALIASES = {
    "category": "category_uid",
}

LOCAL_FILTER_AGGREGATIONS: list[dict[str, Any]] = []

FILTER_OPTIONS_QUERY = """
query FilterOptions {
  products(pageSize: 1, search: "") {
    aggregations {
      attribute_code
      label
      options {
        label
        value
        count
      }
    }
  }
}
"""

FILTER_OPTIONS_TTL_SECONDS = 900
_filter_options_cache: dict[str, Any] = {"expires_at": 0.0, "aggregations": {}}
FILTER_PROMPT_MAX_OPTIONS_PER_FILTER = 20

PRODUCT_FIELDS = """
total_count
items {
  id
  name
  sku
  url_key
  stock_status
  description {
    html
  }
  short_description {
    html
  }
  price_range {
    minimum_price {
      regular_price {
        value
        currency
      }
    }
  }
  image {
    url
    label
  }
  media_gallery {
    url
    label
  }
}
"""


def _post_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    logger.info(
        "[MagentoGraphQL] POST %s variables=%s",
        settings.MAGENTO_GRAPHQL_URL,
        json.dumps(variables, ensure_ascii=True, sort_keys=True),
    )
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        settings.MAGENTO_GRAPHQL_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "[MagentoGraphQL] HTTPError status=%s reason=%s url=%s variables=%s body=%s",
            exc.code,
            getattr(exc, "reason", ""),
            settings.MAGENTO_GRAPHQL_URL,
            json.dumps(variables, ensure_ascii=True, sort_keys=True),
            body,
        )
        raise RuntimeError(f"Magento GraphQL HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        logger.error(
            "[MagentoGraphQL] URLError url=%s variables=%s reason=%s",
            settings.MAGENTO_GRAPHQL_URL,
            json.dumps(variables, ensure_ascii=True, sort_keys=True),
            exc.reason,
        )
        raise RuntimeError(f"Magento GraphQL request failed: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Magento GraphQL returned invalid JSON") from exc

    errors = parsed.get("errors") or []
    if errors:
        message = "; ".join(
            error.get("message", "Unknown GraphQL error") for error in errors
        )
        logger.error(
            "[MagentoGraphQL] errors=%s", json.dumps(errors, ensure_ascii=True)
        )
        raise RuntimeError(f"Magento GraphQL error: {message}")

    data = parsed.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Magento GraphQL returned no data payload")

    product_payload = data.get("products", {})
    logger.info(
        "[MagentoGraphQL] total_count=%s returned_items=%s",
        product_payload.get("total_count"),
        len(product_payload.get("items", []) or []),
    )

    return data


def _products_query(include_filter: bool) -> str:
    if include_filter:
        return f"""
query SearchProducts(
  $search: String!
  $pageSize: Int!
  $currentPage: Int!
  $filter: ProductAttributeFilterInput!
) {{
  products(
    search: $search
    pageSize: $pageSize
    currentPage: $currentPage
    filter: $filter
  ) {{
    {PRODUCT_FIELDS}
  }}
}}
"""
    return f"""
query SearchProducts(
  $search: String!
  $pageSize: Int!
  $currentPage: Int!
) {{
  products(
    search: $search
    pageSize: $pageSize
    currentPage: $currentPage
  ) {{
    {PRODUCT_FIELDS}
  }}
}}
"""


def _normalize_text(value: str) -> str:
    normalized = unescape(value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _sanitize_search_query(
    user_request: str,
    query: str,
    attribute_filters: dict[str, Any],
    name: str,
) -> str:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return ""

    normalized_user_request = str(user_request or "").strip()
    if normalized_user_request and _normalize_text(normalized_query) == _normalize_text(
        normalized_user_request
    ):
        return ""

    if _is_present(name):
        return normalized_query

    if attribute_filters:
        lowered_query = _normalize_text(normalized_query)
        generic_tokens = {
            "i",
            "want",
            "to",
            "see",
            "show",
            "me",
            "products",
            "product",
            "with",
            "in",
            "of",
            "category",
            "size",
            "brand",
            "color",
            "price",
            "under",
            "above",
            "between",
            "for",
        }
        query_tokens = [token for token in lowered_query.split() if token not in generic_tokens]
        attribute_value_tokens: set[str] = set()
        for value in attribute_filters.values():
            attribute_value_tokens.update(_normalize_text(str(value)).split())

        remaining_tokens = [
            token for token in query_tokens if token not in attribute_value_tokens
        ]
        if not remaining_tokens:
            return ""

    return normalized_query


def _extract_numeric_value(text: str) -> float | None:
    matches = re.findall(r"\d+(?:\.\d+)?", str(text).strip().lower())
    if not matches:
        return None
    return float(matches[0])


def _label_matches_numeric_value(label: str, numeric_value: float) -> bool:
    label_text = str(label).strip().lower()
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", label_text)]
    if not numbers:
        return False

    if len(numbers) >= 2:
        low, high = numbers[0], numbers[1]
        return low <= numeric_value <= high

    threshold = numbers[0]
    if any(word in label_text for word in ("below", "under", "less than")):
        return numeric_value < threshold
    if any(word in label_text for word in ("above", "over", "more than")):
        return numeric_value > threshold

    return numeric_value == threshold


def _canonical_attribute_key(key: str) -> str:
    return str(FILTER_ALIASES.get(key, key)).strip()


def _public_attribute_key(canonical_key: str) -> str:
    for public_key, target_key in FILTER_ALIASES.items():
        if str(target_key).strip() == canonical_key:
            return str(public_key).strip()
    return canonical_key


def _merge_aggregation_options(
    base: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_values: set[str] = set()

    for option in [*(base or []), *(extra or [])]:
        value = str(option.get("value", "")).strip()
        if not value or value in seen_values:
            continue
        seen_values.add(value)
        merged.append(option)

    return merged


def _merge_aggregations(
    remote_aggregations: list[dict[str, Any]],
    local_aggregations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    aggregations_by_code: dict[str, dict[str, Any]] = {}

    for aggregation in remote_aggregations:
        code = aggregation.get("attribute_code")
        if not code:
            continue
        aggregations_by_code[str(code)] = {
            "attribute_code": str(code),
            "label": aggregation.get("label", ""),
            "options": aggregation.get("options", []) or [],
        }

    for aggregation in local_aggregations:
        code = aggregation.get("attribute_code")
        if not code:
            continue
        normalized_code = str(code)
        existing = aggregations_by_code.get(normalized_code, {})
        aggregations_by_code[normalized_code] = {
            "attribute_code": normalized_code,
            "label": existing.get("label") or aggregation.get("label", ""),
            "options": _merge_aggregation_options(
                existing.get("options", []) or [],
                aggregation.get("options", []) or [],
            ),
        }

    return aggregations_by_code


def _load_filter_options() -> dict[str, dict[str, Any]]:
    now = time.time()
    if _filter_options_cache["expires_at"] > now:
        return _filter_options_cache["aggregations"]

    local_aggregations = LOCAL_FILTER_AGGREGATIONS
    stale_aggregations = _filter_options_cache.get("aggregations", {}) or {}

    try:
        data = _post_graphql(FILTER_OPTIONS_QUERY, {})
        remote_aggregations = data.get("products", {}).get("aggregations", []) or []
        aggregations_by_code = _merge_aggregations(remote_aggregations, local_aggregations)
    except Exception:
        logger.exception("filter options refresh failed")
        if stale_aggregations:
            logger.info("using stale filter options cache after refresh failure")
            return stale_aggregations
        logger.info("using local filter configuration only after refresh failure")
        aggregations_by_code = _merge_aggregations([], local_aggregations)

    _filter_options_cache["aggregations"] = aggregations_by_code
    _filter_options_cache["expires_at"] = now + FILTER_OPTIONS_TTL_SECONDS
    return aggregations_by_code


def refresh_filter_options_cache() -> dict[str, Any]:
    _filter_options_cache["expires_at"] = 0.0
    aggregations = _load_filter_options()
    return {
        "filterCount": len(aggregations),
        "filters": sorted(_public_attribute_key(key) for key in aggregations.keys()),
    }


def _match_option_value(key: str, raw_value: str) -> str | None:
    canonical_key = _canonical_attribute_key(key)
    normalized_raw = _normalize_filter_value(key, raw_value)
    normalized_text = _normalize_text(normalized_raw)
    if not normalized_text:
        return None

    aggregations_by_code = _load_filter_options()
    aggregation = aggregations_by_code.get(canonical_key)
    if not aggregation:
        logger.info(
            "[FilterResolver] key=%r skipped because it is missing from Magento aggregations and local config",
            key,
        )
        return None

    candidates = aggregation.get("options", []) or []

    if not candidates:
        logger.info(
            "[FilterResolver] key=%r skipped because aggregation has no options",
            key,
        )
        return None

    for option in candidates:
        if str(option.get("value", "")).strip() == normalized_raw:
            return str(option.get("value", "")).strip()

    numeric_value = _extract_numeric_value(normalized_raw)
    if numeric_value is not None:
        numeric_range_matches = [
            option
            for option in candidates
            if _label_matches_numeric_value(str(option.get("label", "")), numeric_value)
        ]
        if numeric_range_matches:
            best = max(
                numeric_range_matches,
                key=lambda option: int(option.get("count", 0) or 0),
            )
            return str(best.get("value", normalized_raw)).strip()

    exact_label_matches = [
        option
        for option in candidates
        if _normalize_text(str(option.get("label", ""))) == normalized_text
    ]
    if exact_label_matches:
        best = max(
            exact_label_matches, key=lambda option: int(option.get("count", 0) or 0)
        )
        return str(best.get("value", normalized_raw)).strip()

    contains_matches = [
        option
        for option in candidates
        if normalized_text in _normalize_text(str(option.get("label", "")))
        or _normalize_text(str(option.get("label", ""))) in normalized_text
    ]
    if contains_matches:
        best = max(
            contains_matches, key=lambda option: int(option.get("count", 0) or 0)
        )
        return str(best.get("value", normalized_raw)).strip()

    logger.info(
        "[FilterResolver] key=%r value=%r skipped because no matching aggregation option was found",
        key,
        raw_value,
    )
    return None


def _available_filter_catalog() -> list[dict[str, Any]]:
    aggregations_by_code = _load_filter_options()
    filters: list[dict[str, Any]] = []

    for canonical_key in sorted(aggregations_by_code.keys()):
        aggregation = aggregations_by_code[canonical_key]
        filters.append(
            {
                "key": _public_attribute_key(canonical_key),
                "attribute_code": canonical_key,
                "label": aggregation.get("label", ""),
                "options": [
                    {
                        "label": option.get("label", ""),
                        "value": str(option.get("value", "")).strip(),
                        "count": option.get("count", 0),
                    }
                    for option in (aggregation.get("options", []) or [])
                    if str(option.get("value", "")).strip()
                ],
            }
        )

    return filters


def build_filter_prompt_context() -> str:
    filters = _available_filter_catalog()
    if not filters:
        return (
            "## Runtime Storefront Filter Context\n"
            "- No live filter catalog is currently available.\n"
            "- Use only broad product search, price, pagination, and exact product details.\n"
        )

    lines = [
        "## Runtime Storefront Filter Context",
        "- Use only the filters and option labels listed below for `search_products`.",
        "- Put non-price filters inside the `attributes` object.",
        "- Backend will map labels to Magento GraphQL filter values.",
        "- If a requested filter or value is missing below, ask one short clarification question.",
        "",
    ]

    for item in filters:
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        options = item.get("options", []) or []
        option_labels = [
            str(option.get("label", "")).strip()
            for option in options
            if str(option.get("label", "")).strip()
        ]
        option_labels = option_labels[:FILTER_PROMPT_MAX_OPTIONS_PER_FILTER]
        label = str(item.get("label", "")).strip() or key
        if option_labels:
            lines.append(f"- {key} ({label}): {', '.join(option_labels)}")
        else:
            lines.append(f"- {key} ({label})")

    return "\n".join(lines)


def _available_option_labels(attribute_key: str) -> list[str]:
    canonical_key = _canonical_attribute_key(attribute_key)
    aggregation = _load_filter_options().get(canonical_key, {})
    labels: list[str] = []
    for option in aggregation.get("options", []) or []:
        label = str(option.get("label", "")).strip()
        if label:
            labels.append(label)
    return labels


def _build_validation_error(
    *,
    message: str,
    unsupported_attribute_filters: dict[str, Any],
    question: str,
    query: str,
    name: str,
    price: str,
    min_price: float | None,
    max_price: float | None,
    page: int,
    page_size: int,
    attribute_filters: dict[str, Any],
) -> dict[str, Any]:
    available_options = {
        key: _available_option_labels(key)
        for key in unsupported_attribute_filters
        if _available_option_labels(key)
    }
    return {
        "validationError": {
            "message": message,
            "unsupportedAttributes": unsupported_attribute_filters,
            "question": question,
            "availableOptions": available_options,
        },
        "items": [],
        "pagination": _pagination(0, page, page_size),
        "paginationCommands": {},
        "searchMeta": _search_meta(
            query=query,
            name=name,
            price=price,
            min_price=min_price,
            max_price=max_price,
            page=page,
            page_size=page_size,
            attribute_filters=attribute_filters,
            unsupported_attribute_filters=unsupported_attribute_filters,
        ),
    }


def _first_validation_question(
    unsupported_attribute_filters: dict[str, Any],
) -> str:
    if not unsupported_attribute_filters:
        return "Could you clarify which filter you want to use?"

    attribute, requested = next(iter(unsupported_attribute_filters.items()))
    labels = _available_option_labels(attribute)
    if labels:
        return (
            f"I can't find {requested} for {attribute}. "
            f"Would you like to see other {attribute} options?"
        )
    return (
        f"I can't filter by {attribute} on this storefront. "
        f"Would you like me to continue without it?"
    )


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(_is_present(item) for item in value)
    return True


def _coerce_filter_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            if _is_present(item):
                values.append(str(item).strip())
        return values
    if value is None:
        return []
    return [str(value).strip()]


def _normalize_filter_value(key: str, value: str) -> str:
    del key
    return value.strip()


def _parse_price_value(
    price: str | None,
    min_price: float | None,
    max_price: float | None,
) -> tuple[float | None, float | None]:
    if not _is_present(price):
        return min_price, max_price

    price_text = str(price).strip().lower()
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", price_text)]

    if not numbers:
        return min_price, max_price

    if "under" in price_text or "below" in price_text or "<" in price_text:
        return min_price, numbers[0]

    if (
        "above" in price_text
        or "over" in price_text
        or "more than" in price_text
        or ">" in price_text
    ):
        return numbers[0], max_price

    if len(numbers) >= 2:
        return numbers[0], numbers[1]

    if min_price is None and max_price is None:
        return numbers[0], numbers[0]

    return min_price, max_price


def _attribute_filter_clause(key: str, value: Any) -> dict[str, Any] | None:
    values = _coerce_filter_values(value)
    if not values:
        return None
    normalized_values: list[str] = []
    for item in values:
        normalized_item = _normalize_filter_value(key, item)
        resolved_item = _match_option_value(key, normalized_item)
        if resolved_item and resolved_item not in normalized_values:
            normalized_values.append(resolved_item)
    if not normalized_values:
        return None
    if len(normalized_values) == 1:
        return {"eq": normalized_values[0]}
    return {"in": normalized_values}


def _build_filter(
    min_price: float | None = None,
    max_price: float | None = None,
    slug: str | None = None,
    name: str = "",
    attribute_filters: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    filter_input: dict[str, Any] = {}

    if slug:
        filter_input["url_key"] = {"eq": slug}

    if _is_present(name):
        filter_input["name"] = {"match": str(name).strip()}

    if min_price is not None or max_price is not None:
        price_filter: dict[str, str] = {}
        if min_price is not None:
            price_filter["from"] = _normalize_price(min_price)
        if max_price is not None:
            price_filter["to"] = _normalize_price(max_price)
        filter_input["price"] = price_filter

    for key, raw_value in (attribute_filters or {}).items():
        clause = _attribute_filter_clause(key, raw_value)
        if clause is not None:
            filter_input[_canonical_attribute_key(key)] = clause

    return filter_input or None


def _normalize_price(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _product_url(url_key: str) -> str:
    return f"{settings.MAGENTO_STOREFRONT_URL.rstrip('/')}/{url_key}.html"


def _stock_badge(stock_status: str | None) -> str:
    if (stock_status or "").upper() == "IN_STOCK":
        return "In stock"
    return "Out of stock"


def _strip_html(value: str | None) -> str:
    if not value:
        return ""

    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _price_summary(product: dict[str, Any]) -> tuple[str, float | None]:
    regular_price = (
        product.get("price_range", {}).get("minimum_price", {}).get("regular_price", {})
    )
    value = regular_price.get("value")
    currency = regular_price.get("currency", "")

    if value is None:
        return "", None

    return f"{currency} {value:,.2f}".strip(), value


def _description(product: dict[str, Any]) -> str:
    description = _strip_html(product.get("short_description", {}).get("html"))
    if description:
        return description

    description = _strip_html(product.get("description", {}).get("html"))
    if description:
        return description

    sku = product.get("sku", "")
    if sku:
        return f"SKU: {sku}"

    return "No description available."


def _images(product: dict[str, Any]) -> list[str]:
    images = [
        item.get("url") for item in product.get("media_gallery", []) if item.get("url")
    ]
    if images:
        return images

    main_image = product.get("image", {}).get("url")
    return [main_image] if main_image else []


def _build_list_actions(product: dict[str, Any]) -> list[dict[str, Any]]:
    title = product.get("name", "this product")
    slug = product.get("url_key", "")

    actions = [
        {
            "text": "Get Details",
            "icon": "quickreply",
            "instructions": [
                {
                    "type": "quick_reply",
                    "options": {
                        "message": f"Get details of {title}",
                        "value": f"Get details of {slug}",
                    },
                }
            ],
        }
    ]

    if slug:
        actions.append(
            {
                "text": "View Product",
                "icon": "redirect",
                "instructions": [
                    {
                        "type": "navigate",
                        "options": {"value": _product_url(slug)},
                    }
                ],
            }
        )

    return actions


def _build_detail_actions(product: dict[str, Any]) -> list[dict[str, Any]]:
    slug = product.get("url_key", "")
    if not slug:
        return []

    return [
        {
            "text": "View Product",
            "icon": "redirect",
            "instructions": [
                {
                    "type": "navigate",
                    "options": {"value": _product_url(slug)},
                }
            ],
        }
    ]


def _format_item(product: dict[str, Any]) -> dict[str, Any]:
    price_label, _ = _price_summary(product)
    slug = product.get("url_key", "")

    return {
        "itemId": str(product.get("id", slug or product.get("sku", ""))),
        "slug": slug,
        "title": product.get("name", ""),
        "description": _description(product),
        "badge": _stock_badge(product.get("stock_status")),
        "highlight": price_label,
        "images": _images(product),
        "url": _product_url(slug) if slug else "",
        "type": "",
        "actions": _build_list_actions(product),
    }


def _pagination(total: int, page: int, page_size: int) -> dict[str, int]:
    total_pages = (total // page_size) + (1 if total % page_size else 0)
    return {
        "pageNo": page,
        "pageSize": page_size,
        "totalPages": max(total_pages, 1) if total > 0 else 0,
        "totalItems": total,
    }


def _pagination_command(
    query: str,
    page: int,
    min_price: float | None,
    max_price: float | None,
    name: str,
    attribute_filters: dict[str, Any],
) -> str:
    parts = [f"PAGINATE_PRODUCTS page={page}", f'query="{query}"']
    if _is_present(name):
        parts.append(f"name={json.dumps(str(name), ensure_ascii=True)}")
    if min_price is not None:
        parts.append(f"min_price={_normalize_price(min_price)}")
    if max_price is not None:
        parts.append(f"max_price={_normalize_price(max_price)}")
    if attribute_filters:
        parts.append(
            f"attributes={json.dumps(attribute_filters, ensure_ascii=True, sort_keys=True)}"
        )
    return " ".join(parts)


def _pagination_meta(
    pagination: dict[str, int],
    query: str,
    min_price: float | None,
    max_price: float | None,
    name: str,
    attribute_filters: dict[str, Any],
) -> dict[str, str]:
    page = pagination["pageNo"]
    total_pages = pagination["totalPages"]
    commands: dict[str, str] = {}

    if page > 1:
        commands["previous"] = _pagination_command(
            query=query,
            page=page - 1,
            min_price=min_price,
            max_price=max_price,
            name=name,
            attribute_filters=attribute_filters,
        )
    if total_pages and page < total_pages:
        commands["next"] = _pagination_command(
            query=query,
            page=page + 1,
            min_price=min_price,
            max_price=max_price,
            name=name,
            attribute_filters=attribute_filters,
        )

    return commands


def _search_meta(
    query: str,
    name: str,
    price: str,
    min_price: float | None,
    max_price: float | None,
    page: int,
    page_size: int,
    attribute_filters: dict[str, Any],
    unsupported_attribute_filters: dict[str, Any],
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "query": query,
        "name": name,
        "price": price,
        "minPrice": min_price,
        "maxPrice": max_price,
        "page": page,
        "pageSize": page_size,
    }
    for key, value in attribute_filters.items():
        if _is_present(value):
            meta[key] = value
    if unsupported_attribute_filters:
        meta["unsupportedAttributes"] = unsupported_attribute_filters
    return meta


def _collect_attribute_filters(dynamic_filters: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(dynamic_filters, dict):
        return {}

    collected: dict[str, Any] = {}
    for key, value in dynamic_filters.items():
        normalized_key = str(key).strip()
        if normalized_key and _is_present(value):
            collected[normalized_key] = value
    return collected


def _split_attribute_filters(
    attribute_filters: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    applied: dict[str, Any] = {}
    unsupported: dict[str, Any] = {}

    for key, value in attribute_filters.items():
        clause = _attribute_filter_clause(key, value)
        if clause is None:
            unsupported[key] = value
            continue
        applied[key] = value

    return applied, unsupported


def _fetch_products(
    query: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = 1,
    page_size: int | None = None,
    slug: str | None = None,
    name: str = "",
    attribute_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_page_size = page_size or settings.MAGENTO_PAGE_SIZE
    filter_input = _build_filter(
        min_price=min_price,
        max_price=max_price,
        slug=slug,
        name=name,
        attribute_filters=attribute_filters,
    )
    variables = {
        "search": query,
        "pageSize": effective_page_size,
        "currentPage": page,
    }
    if filter_input is not None:
        variables["filter"] = filter_input

    data = _post_graphql(_products_query(filter_input is not None), variables)
    return data.get("products", {"items": [], "total_count": 0})


def search_products(
    query: str = "",
    name: str = "",
    price: str = "",
    attributes: dict[str, Any] | None = None,
    user_request: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> dict[str, Any]:
    """Search Magento products with search text and catalog filters."""
    resolved_min_price, resolved_max_price = _parse_price_value(
        price=price,
        min_price=min_price,
        max_price=max_price,
    )
    requested_attribute_filters = _collect_attribute_filters(attributes)
    effective_page_size = page_size or settings.MAGENTO_PAGE_SIZE

    resolved_query = query
    active_attribute_filters, unsupported_attribute_filters = _split_attribute_filters(
        requested_attribute_filters
    )

    if unsupported_attribute_filters:
        return _build_validation_error(
            message="Some requested filters are not available for this storefront.",
            unsupported_attribute_filters=unsupported_attribute_filters,
            question=_first_validation_question(unsupported_attribute_filters),
            query=resolved_query,
            name=name,
            price=price,
            min_price=resolved_min_price,
            max_price=resolved_max_price,
            page=page,
            page_size=effective_page_size,
            attribute_filters=active_attribute_filters,
        )

    resolved_query = _sanitize_search_query(
        user_request=user_request,
        query=resolved_query,
        attribute_filters=active_attribute_filters,
        name=name,
    )

    logger.info(
        "[ToolCall] search_products params=%s",
        json.dumps(
            {
                "query": resolved_query,
                "name": name,
                "price": price,
                "min_price": resolved_min_price,
                "max_price": resolved_max_price,
                "page": page,
                "page_size": page_size or settings.MAGENTO_PAGE_SIZE,
                **active_attribute_filters,
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
    )

    payload = _fetch_products(
        query=resolved_query,
        min_price=resolved_min_price,
        max_price=resolved_max_price,
        page=page,
        page_size=page_size,
        name=name,
        attribute_filters=active_attribute_filters,
    )
    items = [_format_item(product) for product in payload.get("items", [])]
    total = int(payload.get("total_count", 0))
    effective_page_size = page_size or settings.MAGENTO_PAGE_SIZE
    pagination = _pagination(total, page, effective_page_size)

    return {
        "items": items,
        "pagination": pagination,
        "paginationCommands": _pagination_meta(
            pagination=pagination,
            query=resolved_query,
            min_price=resolved_min_price,
            max_price=resolved_max_price,
            name=name,
            attribute_filters=active_attribute_filters,
        ),
        "searchMeta": _search_meta(
            query=resolved_query,
            name=name,
            price=price,
            min_price=resolved_min_price,
            max_price=resolved_max_price,
            page=page,
            page_size=effective_page_size,
            attribute_filters=active_attribute_filters,
            unsupported_attribute_filters={},
        ),
    }


def get_product_by_slug(slug: str) -> dict[str, Any] | None:
    """Get a single Magento product by url_key."""
    logger.info("[ToolCall] get_product_by_slug slug=%r", slug)
    payload = _fetch_products(slug=slug, page_size=1)
    items = payload.get("items", [])
    if not items:
        return None

    product = items[0]
    price_label, _ = _price_summary(product)

    return {
        "itemId": str(product.get("id", slug or product.get("sku", ""))),
        "slug": product.get("url_key", slug),
        "badge": _stock_badge(product.get("stock_status")),
        "header": product.get("sku", ""),
        "title": product.get("name", ""),
        "description": _description(product),
        "highlight": price_label,
        "subText": f"SKU: {product.get('sku', '')}".strip(),
        "footer": "Open the product page for full Magento details.",
        "type": "",
        "images": _images(product),
        "actions": _build_detail_actions(product),
    }


def get_similar_products(product_type: str) -> dict[str, Any]:
    """Fallback keyword-based related products search."""

    keyword = product_type.replace("type:", "").strip()
    logger.info("[ToolCall] get_similar_products keyword=%r", keyword)
    payload = _fetch_products(query=keyword, page_size=4)
    items = [_format_item(product) for product in payload.get("items", [])]

    return {
        "items": items,
        "pagination": _pagination(len(items), 1, 4),
    }

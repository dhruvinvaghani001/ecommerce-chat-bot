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

ATTRIBUTE_FILTER_KEYS = (
    "category",
    "climate",
    "collar",
    "color",
    "eco_collection",
    "erin_recommends",
    "features_bags",
    "format",
    "gender",
    "material",
    "pattern",
    "performance_fabric",
    "sale",
    "size",
    "sleeve",
    "strap_bags",
    "style_bags",
    "style_bottom",
    "style_general",
)

FILTER_VALUE_ALIASES: dict[str, dict[str, str]] = {
    "gender": {
        "male": "men",
        "man": "men",
        "men": "men",
        "mens": "men",
        "boy": "men",
        "boys": "men",
        "female": "women",
        "woman": "women",
        "women": "women",
        "womens": "women",
        "lady": "women",
        "ladies": "women",
        "girl": "women",
        "girls": "women",
    }
}

FILTER_AGGREGATION_CODES: dict[str, tuple[str, ...]] = {
    "category": ("category_uid", "category_gear"),
    "climate": ("climate",),
    "collar": ("collar",),
    "color": ("color",),
    "eco_collection": ("eco_collection",),
    "erin_recommends": ("erin_recommends",),
    "features_bags": ("features_bags",),
    "format": ("format",),
    "gender": ("gender",),
    "material": ("material",),
    "pattern": ("pattern",),
    "performance_fabric": ("performance_fabric",),
    "sale": ("sale",),
    "size": ("size",),
    "sleeve": ("sleeve",),
    "strap_bags": ("strap_bags",),
    "style_bags": ("style_bags",),
    "style_bottom": ("style_bottom",),
    "style_general": ("style_general",),
}

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

CATEGORY_TREE_QUERY = """
query CategoryTree {
  categoryList {
    id
    name
    url_key
    level
    path
    children {
      id
      name
      url_key
      level
      path
      children {
        id
        name
        url_key
        level
        path
        children {
          id
          name
          url_key
          level
          path
        }
      }
    }
  }
}
"""

FILTER_OPTIONS_TTL_SECONDS = 900
_filter_options_cache: dict[str, Any] = {"expires_at": 0.0, "options": {}}
_category_tree_cache: dict[str, Any] = {"expires_at": 0.0, "categories": []}

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
        raise RuntimeError(f"Magento GraphQL HTTP {exc.code}: {body}") from exc
    except URLError as exc:
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
        logger.error("[MagentoGraphQL] errors=%s", json.dumps(errors, ensure_ascii=True))
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


def _load_filter_options() -> dict[str, list[dict[str, Any]]]:
    now = time.time()
    if _filter_options_cache["expires_at"] > now:
        return _filter_options_cache["options"]

    data = _post_graphql(FILTER_OPTIONS_QUERY, {})
    aggregations = data.get("products", {}).get("aggregations", []) or []
    options_by_code: dict[str, list[dict[str, Any]]] = {}

    for aggregation in aggregations:
        code = aggregation.get("attribute_code")
        if not code:
            continue
        options_by_code[code] = aggregation.get("options", []) or []

    _filter_options_cache["options"] = options_by_code
    _filter_options_cache["expires_at"] = now + FILTER_OPTIONS_TTL_SECONDS
    return options_by_code


def _flatten_categories(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for node in nodes:
        flattened.append(
            {
                "id": str(node.get("id", "")).strip(),
                "name": str(node.get("name", "")).strip(),
                "url_key": str(node.get("url_key", "")).strip(),
                "level": node.get("level"),
                "path": str(node.get("path", "")).strip(),
            }
        )
        children = node.get("children", []) or []
        if children:
            flattened.extend(_flatten_categories(children))
    return flattened


def _load_category_tree() -> list[dict[str, Any]]:
    now = time.time()
    if _category_tree_cache["expires_at"] > now:
        return _category_tree_cache["categories"]

    data = _post_graphql(CATEGORY_TREE_QUERY, {})
    categories = _flatten_categories(data.get("categoryList", []) or [])
    _category_tree_cache["categories"] = categories
    _category_tree_cache["expires_at"] = now + FILTER_OPTIONS_TTL_SECONDS
    return categories


def _resolve_category_id(raw_value: str) -> str:
    normalized = raw_value.strip()
    if not normalized:
        return normalized
    if normalized.isdigit():
        return normalized

    categories = _load_category_tree()
    normalized_text = _normalize_text(normalized)
    if not normalized_text:
        return normalized

    for category in categories:
        if category["id"] == normalized:
            return category["id"]

    exact_matches = [
        category
        for category in categories
        if _normalize_text(category["name"]) == normalized_text
        or _normalize_text(category["url_key"]) == normalized_text
    ]
    if exact_matches:
        best = min(
            exact_matches,
            key=lambda category: (int(category.get("level") or 999), len(category["path"])),
        )
        return best["id"]

    contains_matches = [
        category
        for category in categories
        if normalized_text in _normalize_text(category["name"])
        or normalized_text in _normalize_text(category["url_key"])
    ]
    if contains_matches:
        best = min(
            contains_matches,
            key=lambda category: (int(category.get("level") or 999), len(category["path"])),
        )
        return best["id"]

    return normalized


def _match_option_value(key: str, raw_value: str) -> str:
    option_codes = FILTER_AGGREGATION_CODES.get(key, (key,))
    normalized_raw = _normalize_filter_value(key, raw_value)
    normalized_text = _normalize_text(normalized_raw)
    if not normalized_text:
        return normalized_raw

    options_by_code = _load_filter_options()
    candidates: list[dict[str, Any]] = []
    for code in option_codes:
        candidates.extend(options_by_code.get(code, []))

    if not candidates:
        return normalized_raw

    for option in candidates:
        if str(option.get("value", "")).strip() == normalized_raw:
            return str(option.get("value", "")).strip()

    exact_label_matches = [
        option
        for option in candidates
        if _normalize_text(str(option.get("label", ""))) == normalized_text
    ]
    if exact_label_matches:
        best = max(exact_label_matches, key=lambda option: int(option.get("count", 0) or 0))
        return str(best.get("value", normalized_raw)).strip()

    contains_matches = [
        option
        for option in candidates
        if normalized_text in _normalize_text(str(option.get("label", "")))
        or _normalize_text(str(option.get("label", ""))) in normalized_text
    ]
    if contains_matches:
        best = max(contains_matches, key=lambda option: int(option.get("count", 0) or 0))
        return str(best.get("value", normalized_raw)).strip()

    return normalized_raw


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
    normalized = value.strip()
    if not normalized:
        return normalized

    alias_map = FILTER_VALUE_ALIASES.get(key, {})
    return alias_map.get(normalized.lower(), normalized)


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

    if "above" in price_text or "over" in price_text or "more than" in price_text or ">" in price_text:
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
        if key == "gender":
            resolved_item = normalized_item
        else:
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

    category_value = (attribute_filters or {}).get("category")
    if _is_present(category_value):
        category_values = _coerce_filter_values(category_value)
        resolved_category_ids: list[str] = []
        for item in category_values:
            resolved_id = _resolve_category_id(item)
            if resolved_id and resolved_id not in resolved_category_ids:
                resolved_category_ids.append(resolved_id)
        if resolved_category_ids:
            if len(resolved_category_ids) == 1:
                filter_input["category_id"] = {"eq": resolved_category_ids[0]}
            else:
                filter_input["category_id"] = {"in": resolved_category_ids}

    for key in ATTRIBUTE_FILTER_KEYS:
        if key == "category":
            continue
        raw_value = (attribute_filters or {}).get(key)
        clause = _attribute_filter_clause(key, raw_value)
        if clause is not None:
            filter_input[key] = clause

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
        product.get("price_range", {})
        .get("minimum_price", {})
        .get("regular_price", {})
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
        item.get("url")
        for item in product.get("media_gallery", [])
        if item.get("url")
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
    parts = [f'PAGINATE_PRODUCTS page={page}', f'query="{query}"']
    if _is_present(name):
        parts.append(f'name={json.dumps(str(name), ensure_ascii=True)}')
    if min_price is not None:
        parts.append(f"min_price={_normalize_price(min_price)}")
    if max_price is not None:
        parts.append(f"max_price={_normalize_price(max_price)}")
    for key in ATTRIBUTE_FILTER_KEYS:
        value = attribute_filters.get(key)
        if _is_present(value):
            parts.append(f"{key}={json.dumps(str(value), ensure_ascii=True)}")
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
    page_size: int | None = None,
) -> dict[str, Any]:
    """Search Magento products with search text and catalog filters."""
    resolved_min_price, resolved_max_price = _parse_price_value(
        price=price,
        min_price=min_price,
        max_price=max_price,
    )
    attribute_filters = {
        "category": category,
        "climate": climate,
        "collar": collar,
        "color": color,
        "eco_collection": eco_collection,
        "erin_recommends": erin_recommends,
        "features_bags": features_bags,
        "format": format,
        "gender": gender,
        "material": material,
        "pattern": pattern,
        "performance_fabric": performance_fabric,
        "sale": sale,
        "size": size,
        "sleeve": sleeve,
        "strap_bags": strap_bags,
        "style_bags": style_bags,
        "style_bottom": style_bottom,
        "style_general": style_general,
    }
    active_attribute_filters = {
        key: value for key, value in attribute_filters.items() if _is_present(value)
    }

    logger.info(
        "[ToolCall] search_products params=%s",
        json.dumps(
            {
                "query": query,
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
        query=query,
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
            query=query,
            min_price=resolved_min_price,
            max_price=resolved_max_price,
            name=name,
            attribute_filters=active_attribute_filters,
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


def get_similar_products(product_type: str, exclude_slug: str = "") -> dict[str, Any]:
    """Fallback keyword-based related products search."""
    del exclude_slug

    keyword = product_type.replace("type:", "").strip()
    logger.info("[ToolCall] get_similar_products keyword=%r", keyword)
    payload = _fetch_products(query=keyword, page_size=4)
    items = [_format_item(product) for product in payload.get("items", [])]

    return {
        "items": items,
        "pagination": _pagination(len(items), 1, 4),
    }

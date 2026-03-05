from .data import PRODUCTS

DOMAIN = "example-realestate.com"


def _build_actions(product: dict) -> list[dict]:
    return [
        {
            "text": "Get Details",
            "icon": "quickreply",
            "instructions": [
                {
                    "type": "quick_reply",
                    "options": {
                        "message": f"Get Details of {product['title']}",
                        "value": f"Get Details of {product['slug']}",
                    },
                }
            ],
        },
        {
            "text": "Show Similar",
            "icon": "similar",
            "instructions": [
                {
                    "type": "quick_reply",
                    "options": {
                        "message": f"Get similar products to {product['title']}",
                        "value": f"Get similar products to type:{product['type']}",
                    },
                }
            ],
        },
        {
            "text": "View",
            "icon": "redirect",
            "instructions": [
                {
                    "type": "navigate",
                    "options": {
                        "value": f"https://{DOMAIN}/product/{product['slug']}"
                    },
                }
            ],
        },
    ]


def _badge(product: dict) -> str:
    count = product.get("inventory_count", 0)
    if count > 5:
        return "In stock"
    if count > 0:
        return "Limited"
    return "Sold Out"


def _format_item(product: dict) -> dict:
    return {
        "itemId": product["id"],
        "slug": product["slug"],
        "title": product["title"],
        "description": product["description"],
        "badge": _badge(product),
        "highlight": f"{product['currency']} {product['price']:,.2f}",
        "images": product.get("images", {}).get("images", []),
        "url": f"https://{DOMAIN}/product/{product['slug']}",
        "type": product.get("type", ""),
        "actions": _build_actions(product),
    }


def search_products(
    query: str = "",
    product_type: str = "",
    location: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search products with optional filters."""
    results = PRODUCTS[:]

    if query:
        q = query.lower()
        results = [
            p
            for p in results
            if q in p["title"].lower()
            or q in p["description"].lower()
            or q in p.get("location", "").lower()
            or any(q in cat.lower() for cat in p.get("categories", []))
        ]

    if product_type:
        t = product_type.lower()
        results = [p for p in results if p.get("type", "").lower() == t]

    if location:
        loc = location.lower()
        results = [p for p in results if loc in p.get("location", "").lower()]

    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]

    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = results[start:end]

    items = [_format_item(p) for p in page_items]
    pagination = {
        "pageNo": page,
        "pageSize": page_size,
        "totalPages": (total // page_size) + (1 if total % page_size > 0 else 0),
        "totalItems": total,
    }

    return {"items": items, "pagination": pagination}


def get_product_by_slug(slug: str) -> dict | None:
    """Get a single product's full details by slug."""
    slug_lower = slug.lower().strip()
    for p in PRODUCTS:
        if p["slug"].lower() == slug_lower:
            inv = p.get("inventory_count", 0)
            badge = "In stock" if inv > 5 else ("Limited" if inv > 0 else "Sold Out")
            return {
                "itemId": p["id"],
                "slug": p["slug"],
                "badge": badge,
                "header": f"{p.get('rating', 0)} ⭐",
                "title": p["title"],
                "description": p["description"],
                "highlight": f"{p['currency']} {p['price']:,.2f}",
                "subText": f"Location: {p.get('location', 'N/A')}",
                "footer": "Click the button for further actions",
                "type": p.get("type", ""),
                "images": p.get("images", {}).get("images", []),
                "actions": [
                    {
                        "text": "Contact Agent",
                        "icon": "redirect",
                        "instructions": [
                            {
                                "type": "navigate",
                                "options": {
                                    "value": f"https://{DOMAIN}/contact?product={p['slug']}"
                                },
                            }
                        ],
                    },
                    {
                        "text": "Show Similar",
                        "icon": "similar",
                        "instructions": [
                            {
                                "type": "quick_reply",
                                "options": {
                                    "message": f"Get similar products to {p['title']}",
                                    "value": f"Get similar products to type:{p['type']}",
                                },
                            }
                        ],
                    },
                    {
                        "text": "View",
                        "icon": "redirect",
                        "instructions": [
                            {
                                "type": "navigate",
                                "options": {
                                    "value": f"https://{DOMAIN}/product/{p['slug']}"
                                },
                            }
                        ],
                    },
                ],
            }
    return None


def get_similar_products(product_type: str, exclude_slug: str = "") -> dict:
    """Get products of similar type."""
    t = product_type.lower().replace("type:", "").strip()
    results = [
        p for p in PRODUCTS if p.get("type", "").lower() == t and p["slug"] != exclude_slug
    ]
    if not results:
        results = PRODUCTS[:4]

    items = [_format_item(p) for p in results]
    return {
        "items": items,
        "pagination": {
            "pageNo": 1,
            "pageSize": 20,
            "totalPages": 1,
            "totalItems": len(items),
        },
    }

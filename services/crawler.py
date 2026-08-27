"""Fetches real product listings for a search query from external APIs.

Amazon and AliExpress go through third-party RapidAPI-hosted wrappers
("Real-Time Amazon Data" and "AliExpress DataHub") since neither
platform offers a self-serve official search API. eBay uses eBay's own
Browse API via OAuth2 client-credentials, but returns no results until
EBAY_CLIENT_ID/EBAY_CLIENT_SECRET are set (eBay approval pending).

Each fetcher returns up to MAX_LISTINGS_PER_SITE relevant listings (not
just the top match), so results look like a real marketplace rather
than one card per site. A site that errors, times out, or isn't
configured yet simply contributes no listings rather than failing the
whole search.
"""

import time

import requests

from config import Config

SITES = ["Amazon", "AliExpress", "eBay"]

REQUEST_TIMEOUT = 10
MAX_LISTINGS_PER_SITE = 6

_ebay_token_cache = {"access_token": None, "expires_at": 0}


def _to_kes(usd_amount):
    return round(usd_amount * Config.USD_TO_KES_RATE, 2)


def _is_relevant(query, title):
    """True if the listing title actually shares a word with the query.

    Some upstream search APIs (notably AliExpress's) fall back to unrelated
    filler results instead of an empty list when nothing matches — this
    catches that instead of trusting "the API returned something" as proof
    of a real match.
    """
    query_words = {w for w in query.lower().split() if len(w) >= 3}
    if not query_words:
        return True
    title_lower = (title or "").lower()
    return any(word in title_lower for word in query_words)


def _absolute_url(url):
    """AliExpress returns protocol-relative URLs ("//...") for links/images."""
    url = url or ""
    return f"https:{url}" if url.startswith("//") else url or None


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def fetch_from_amazon(query):
    if not Config.RAPIDAPI_AMAZON_KEY:
        return []

    try:
        response = requests.get(
            f"https://{Config.RAPIDAPI_AMAZON_HOST}/search",
            params={
                "query": query,
                "page": 1,
                "country": "US",
                "sort_by": "RELEVANCE",
                "product_condition": "ALL",
                "is_prime": "false",
                "deals_and_discounts": "NONE",
            },
            headers={
                "x-rapidapi-host": Config.RAPIDAPI_AMAZON_HOST,
                "x-rapidapi-key": Config.RAPIDAPI_AMAZON_KEY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        products = response.json().get("data", {}).get("products", [])
    except (requests.RequestException, ValueError):
        return []

    listings = []
    for product in products:
        if len(listings) >= MAX_LISTINGS_PER_SITE:
            break
        price_usd = _parse_float(product.get("product_price"))
        title = product.get("product_title", query)
        if price_usd is None or not _is_relevant(query, title):
            continue
        listings.append({
            "site": "Amazon",
            "title": title,
            "price": _to_kes(price_usd),
            "rating": _parse_float(product.get("product_star_rating")) or 0.0,
            "num_ratings": int(product.get("product_num_ratings") or 0),
            "pay_on_delivery": False,
            "url": product.get("product_url"),
            "image": product.get("product_photo"),
        })
    return listings


def fetch_from_aliexpress(query, _retries=2):
    if not Config.RAPIDAPI_ALIEXPRESS_KEY:
        return []

    for attempt in range(_retries):
        try:
            response = requests.get(
                f"https://{Config.RAPIDAPI_ALIEXPRESS_HOST}/item_search_2",
                params={"q": query, "page": 1, "sort": "default"},
                headers={
                    "x-rapidapi-host": Config.RAPIDAPI_ALIEXPRESS_HOST,
                    "x-rapidapi-key": Config.RAPIDAPI_ALIEXPRESS_KEY,
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("result", {}).get("status", {}).get("data") != "success":
                continue
            results = body["result"].get("resultList", [])
            break
        except (requests.RequestException, ValueError, KeyError):
            results = []
            continue
    else:
        return []

    listings = []
    for entry in results:
        if len(listings) >= MAX_LISTINGS_PER_SITE:
            break
        item = entry.get("item", {})
        sku = item.get("sku", {}).get("def", {})
        price_usd = _parse_float(sku.get("promotionPrice")) or _parse_float(sku.get("price"))
        title = item.get("title", query)
        if price_usd is None or not _is_relevant(query, title):
            continue
        listings.append({
            "site": "AliExpress",
            "title": title,
            "price": _to_kes(price_usd),
            "rating": _parse_float(item.get("averageStarRate")) or 0.0,
            # No review-count field in this response tier.
            "num_ratings": 0,
            "pay_on_delivery": False,
            "url": _absolute_url(item.get("itemUrl")),
            "image": _absolute_url(item.get("image")),
        })
    return listings


def _get_ebay_token():
    if not Config.EBAY_CLIENT_ID or not Config.EBAY_CLIENT_SECRET:
        return None

    if _ebay_token_cache["access_token"] and _ebay_token_cache["expires_at"] > time.time():
        return _ebay_token_cache["access_token"]

    try:
        response = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            auth=(Config.EBAY_CLIENT_ID, Config.EBAY_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError):
        return None

    token = body.get("access_token")
    if not token:
        return None

    _ebay_token_cache["access_token"] = token
    _ebay_token_cache["expires_at"] = time.time() + int(body.get("expires_in", 0)) - 60
    return token


def fetch_from_ebay(query):
    token = _get_ebay_token()
    if not token:
        return []

    try:
        response = requests.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            params={"q": query, "limit": MAX_LISTINGS_PER_SITE * 2},
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        items = response.json().get("itemSummaries", [])
    except (requests.RequestException, ValueError):
        return []

    listings = []
    for item in items:
        if len(listings) >= MAX_LISTINGS_PER_SITE:
            break
        price_usd = _parse_float((item.get("price") or {}).get("value"))
        title = item.get("title", query)
        if price_usd is None or not _is_relevant(query, title):
            continue
        seller = item.get("seller") or {}
        # eBay's Browse API has no star rating; feedbackPercentage (0-100) is
        # the closest real signal, scaled onto the same 0-5 range as the others.
        feedback_pct = _parse_float(seller.get("feedbackPercentage"))
        listings.append({
            "site": "eBay",
            "title": title,
            "price": _to_kes(price_usd),
            "rating": round(feedback_pct / 20, 1) if feedback_pct is not None else 0.0,
            "num_ratings": int(seller.get("feedbackScore") or 0),
            "pay_on_delivery": False,
            "url": item.get("itemWebUrl"),
            "image": (item.get("image") or {}).get("imageUrl"),
        })
    return listings


FETCHERS = {
    "Amazon": fetch_from_amazon,
    "AliExpress": fetch_from_aliexpress,
    "eBay": fetch_from_ebay,
}


def fetch_all(query):
    """Query every configured site and return whatever listings came back.

    A site with no credentials configured, or whose request failed, simply
    contributes no listings rather than failing the whole search.
    """
    listings = []
    for fetcher in FETCHERS.values():
        try:
            site_listings = fetcher(query)
        except Exception:
            site_listings = []
        listings.extend(site_listings or [])
    return listings
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
whole search. Per-site failures are logged so operators can tell which
marketplace is down.

Fetchers run concurrently; results for non-empty queries are cached in
Redis when configured, with a bounded in-memory fallback (see services.cache),
so repeated searches don't hit upstream APIs again within the TTL.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait
from math import isfinite

import requests

from config import Config
from services.cache import cache_clear, cache_get, cache_set

SITES = ["Amazon", "AliExpress", "eBay"]

REQUEST_TIMEOUT = Config.MARKETPLACE_TIMEOUT_SECONDS
MAX_LISTINGS_PER_SITE = 6

FETCH_ALL_TIMEOUT = 15
FETCH_ALL_WORKERS = 3

logger = logging.getLogger(__name__)

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
    if not isinstance(url, str):
        return None
    return f"https:{url}" if url.startswith("//") else url or None


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if isfinite(parsed) else None
    try:
        parsed = float(str(value).replace("$", "").replace(",", "").strip())
        return parsed if isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _parse_count(value):
    parsed = _parse_float(value)
    return max(0, int(parsed)) if parsed is not None else 0


def _rating(value):
    parsed = _parse_float(value)
    return round(max(0.0, min(5.0, parsed or 0.0)), 1)


def _object(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _title(value, fallback):
    return value.strip() if isinstance(value, str) and value.strip() else fallback


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
        body = _object(response.json())
        products = _list(_object(body.get("data")).get("products"))
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Amazon fetch failed for %r: %s", query, exc)
        return []

    listings = []
    for product in products:
        if not isinstance(product, dict):
            continue
        if len(listings) >= MAX_LISTINGS_PER_SITE:
            break
        price_usd = _parse_float(product.get("product_price"))
        title = _title(product.get("product_title"), query)
        if price_usd is None or price_usd <= 0 or not _is_relevant(query, title):
            continue
        listings.append({
            "site": "Amazon",
            "title": title,
            "price": _to_kes(price_usd),
            "rating": _rating(product.get("product_star_rating")),
            "num_ratings": _parse_count(product.get("product_num_ratings")),
            "pay_on_delivery": Config.PAY_ON_DELIVERY_DEFAULTS.get("Amazon", False),
            "url": _absolute_url(product.get("product_url")),
            "image": _absolute_url(product.get("product_photo")),
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
            body = _object(response.json())
            result = _object(body.get("result"))
            if _object(result.get("status")).get("data") != "success":
                continue
            results = _list(result.get("resultList"))
            break
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning(
                "AliExpress fetch attempt %d failed for %r: %s",
                attempt + 1,
                query,
                exc,
            )
            results = []
            continue
    else:
        return []

    listings = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if len(listings) >= MAX_LISTINGS_PER_SITE:
            break
        item = _object(entry.get("item"))
        sku = _object(_object(item.get("sku")).get("def"))
        price_usd = _parse_float(sku.get("promotionPrice")) or _parse_float(sku.get("price"))
        title = _title(item.get("title"), query)
        if price_usd is None or price_usd <= 0 or not _is_relevant(query, title):
            continue
        listings.append({
            "site": "AliExpress",
            "title": title,
            "price": _to_kes(price_usd),
            "rating": _rating(item.get("averageStarRate")),
            # No review-count field in this response tier.
            "num_ratings": 0,
            "pay_on_delivery": Config.PAY_ON_DELIVERY_DEFAULTS.get("AliExpress", False),
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
        body = _object(response.json())
    except (requests.RequestException, ValueError) as exc:
        logger.warning("eBay token fetch failed: %s", exc)
        return None

    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        return None

    _ebay_token_cache["access_token"] = token
    _ebay_token_cache["expires_at"] = time.time() + _parse_count(body.get("expires_in")) - 60
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
        items = _list(_object(response.json()).get("itemSummaries"))
    except (requests.RequestException, ValueError) as exc:
        logger.warning("eBay search failed for %r: %s", query, exc)
        return []

    listings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if len(listings) >= MAX_LISTINGS_PER_SITE:
            break
        price_usd = _parse_float(_object(item.get("price")).get("value"))
        title = _title(item.get("title"), query)
        if price_usd is None or price_usd <= 0 or not _is_relevant(query, title):
            continue
        seller = _object(item.get("seller"))
        # eBay's Browse API has no star rating; feedbackPercentage (0-100) is
        # the closest real signal, scaled onto the same 0-5 range as the others.
        feedback_pct = _parse_float(seller.get("feedbackPercentage"))
        listings.append({
            "site": "eBay",
            "title": title,
            "price": _to_kes(price_usd),
            "rating": _rating(feedback_pct / 20 if feedback_pct is not None else 0),
            "num_ratings": _parse_count(seller.get("feedbackScore")),
            "pay_on_delivery": Config.PAY_ON_DELIVERY_DEFAULTS.get("eBay", False),
            "url": _absolute_url(item.get("itemWebUrl")),
            "image": _absolute_url(_object(item.get("image")).get("imageUrl")),
        })
    return listings


FETCHERS = {
    "Amazon": fetch_from_amazon,
    "AliExpress": fetch_from_aliexpress,
    "eBay": fetch_from_ebay,
}


def _fetch_site(site, fetcher, query):
    """Run a single site fetcher, never letting it fail the whole search."""
    try:
        return fetcher(query)
    except Exception as exc:  # keep the per-site try/except
        logger.exception("%s fetcher raised for %r: %s", site, query, exc)
        return []


def clear_cache():
    """Clear the in-memory search-result cache (mainly for tests)."""
    cache_clear()


def fetch_all(query):
    """Query every configured site and return whatever listings came back.

    The three site fetchers run concurrently (max 3 workers) with an overall
    timeout of 15 seconds; unfinished or failed sites contribute no listings.
    Results are keyed on query.strip().lower(); only non-empty results are
    cached.

    Returns a tuple of (listings, site_counts) where site_counts maps each
    site name to the number of listings it contributed. A site with no
    credentials configured, or whose request failed, simply contributes no
    listings rather than failing the whole search.
    """
    key = query.strip().lower()
    cached = cache_get(key)
    if cached is not None:
        return cached["listings"], cached["site_counts"]

    listings = []
    site_counts = {}
    pool = ThreadPoolExecutor(max_workers=FETCH_ALL_WORKERS)
    try:
        futures = {
            pool.submit(_fetch_site, site, fetcher, query): site
            for site, fetcher in FETCHERS.items()
        }
        done, not_done = wait(futures, timeout=FETCH_ALL_TIMEOUT)
        for future in not_done:
            site = futures[future]
            future.cancel()
            site_counts[site] = 0
            logger.info("%s fetcher timed out for %r", site, query)
        for future in done:
            site = futures[future]
            try:
                site_listings = future.result()
            except Exception as exc:  # keep the per-site try/except
                logger.exception("%s fetcher raised for %r: %s", site, query, exc)
                site_listings = []
            site_counts[site] = len(site_listings or [])
            logger.info("%s returned %d listings for %r", site, site_counts[site], query)
            listings.extend(site_listings or [])
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if listings:
        cache_set(key, {"listings": listings, "site_counts": site_counts})
    return listings, site_counts
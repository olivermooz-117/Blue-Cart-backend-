"""Fetches product listings for a search query from each e-commerce site.

Each site's real API call belongs in its own function below. For now they
return mock data shaped like a real API response so the rest of the app
(ranking, filtering) can be built and tested without live API keys.
"""

import random

SITES = ["Amazon", "eBay", "Shopify", "Alibaba"]


def _mock_listing(site, query):
    """Prices are mocked in KES, roughly matching real-world listing amounts."""
    base_price = round(random.uniform(1500, 60000), 2)
    return {
        "site": site,
        "title": query,
        "price": base_price,
        "delivery_cost": round(random.uniform(100, 500), 2),
        "rating": round(random.uniform(3.0, 5.0), 1),
        "num_ratings": random.randint(1, 500),
        "pay_on_delivery": random.choice([True, False]),
    }


def fetch_from_amazon(query):
    return _mock_listing("Amazon", query)


def fetch_from_ebay(query):
    return _mock_listing("eBay", query)


def fetch_from_shopify(query):
    return _mock_listing("Shopify", query)


def fetch_from_alibaba(query):
    return _mock_listing("Alibaba", query)


FETCHERS = {
    "Amazon": fetch_from_amazon,
    "eBay": fetch_from_ebay,
    "Shopify": fetch_from_shopify,
    "Alibaba": fetch_from_alibaba,
}


def fetch_all(query):
    """Query every configured site and return their raw listings."""
    return [fetcher(query) for fetcher in FETCHERS.values()]
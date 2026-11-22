import time

import pytest

from services import crawler


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


@pytest.mark.parametrize(
    ("site", "body"),
    [
        ("amazon", []),
        ("amazon", {"data": {"products": [None, []]}}),
        ("aliexpress", []),
        (
            "aliexpress",
            {
                "result": {
                    "status": {"data": "success"},
                    "resultList": [None, []],
                }
            },
        ),
        ("ebay", []),
        ("ebay", {"itemSummaries": [None, []]}),
    ],
)
def test_malformed_marketplace_responses_do_not_raise(monkeypatch, site, body):
    monkeypatch.setattr(crawler.Config, "RAPIDAPI_AMAZON_KEY", "test-key")
    monkeypatch.setattr(crawler.Config, "RAPIDAPI_ALIEXPRESS_KEY", "test-key")
    monkeypatch.setattr(crawler.Config, "EBAY_CLIENT_ID", "test-id")
    monkeypatch.setattr(crawler.Config, "EBAY_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(crawler, "_ebay_token_cache", {
        "access_token": "test-token",
        "expires_at": time.time() + 60,
    })
    monkeypatch.setattr(crawler.requests, "get", lambda *args, **kwargs: FakeResponse(body))

    if site == "amazon":
        results = crawler.fetch_from_amazon("phone")
    elif site == "aliexpress":
        results = crawler.fetch_from_aliexpress("phone", _retries=1)
    else:
        results = crawler.fetch_from_ebay("phone")

    assert results == []


def test_amazon_normalizes_rating_and_num_ratings(monkeypatch):
    products = [
        {"product_price": "10", "product_title": "phone", "product_star_rating": 9,
         "product_num_ratings": -3},
        {"product_price": "11", "product_title": "phone", "product_star_rating": -1,
         "product_num_ratings": "not-a-number"},
        {"product_price": "12", "product_title": "phone", "product_star_rating": "bad"},
        {"product_price": "13", "product_title": "phone", "product_star_rating": 4.5,
         "product_num_ratings": "1,234"},
        {"product_price": {"amount": 14}, "product_title": "phone"},
    ]
    monkeypatch.setattr(crawler.Config, "RAPIDAPI_AMAZON_KEY", "test-key")
    monkeypatch.setattr(
        crawler.requests, "get", lambda *args, **kwargs: FakeResponse({
            "data": {"products": products}
        })
    )

    results = crawler.fetch_from_amazon("phone")

    assert [item["rating"] for item in results] == [5.0, 0.0, 0.0, 4.5]
    assert [item["num_ratings"] for item in results] == [0, 0, 0, 1234]


@pytest.mark.parametrize("site", ["amazon", "aliexpress", "ebay"])
def test_crawler_passes_site_timeout_to_requests(monkeypatch, site):
    timeouts = []
    monkeypatch.setattr(crawler.Config, "RAPIDAPI_AMAZON_KEY", "test-key")
    monkeypatch.setattr(crawler.Config, "RAPIDAPI_ALIEXPRESS_KEY", "test-key")
    monkeypatch.setattr(crawler.Config, "EBAY_CLIENT_ID", "test-id")
    monkeypatch.setattr(crawler.Config, "EBAY_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(crawler, "REQUEST_TIMEOUT", 3)
    monkeypatch.setattr(crawler, "_ebay_token_cache", {
        "access_token": "test-token",
        "expires_at": time.time() + 60,
    })
    bodies = {
        "amazon": {"data": {"products": []}},
        "aliexpress": {
            "result": {"status": {"data": "success"}, "resultList": []}
        },
        "ebay": {"itemSummaries": []},
    }

    def fake_get(*args, **kwargs):
        timeouts.append(kwargs["timeout"])
        return FakeResponse(bodies[site])

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    if site == "amazon":
        results = crawler.fetch_from_amazon("phone")
    elif site == "aliexpress":
        results = crawler.fetch_from_aliexpress("phone", _retries=1)
    else:
        results = crawler.fetch_from_ebay("phone")
    assert results == []
    assert timeouts == [3]

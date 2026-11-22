from unittest.mock import patch


def test_search_requires_query(client):
    response = client.get("/api/search")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_search_returns_structure(client):
    mock_listings = [
        {
            "site": "Amazon",
            "title": "Test Phone",
            "price": 15000,
            "rating": 4.5,
            "num_ratings": 100,
            "pay_on_delivery": False,
            "url": "https://example.com",
            "image": "https://example.com/img.jpg",
        }
    ]

    with patch(
        "services.crawler.fetch_all",
        return_value=(mock_listings, {"Amazon": 1}),
    ):
        response = client.get("/api/search?q=phone")
        data = response.get_json()

    assert response.status_code == 200
    assert data["query"] == "phone"
    assert "results" in data
    assert len(data["results"]) == 1
    assert "mb_score" in data["results"][0]
    assert "cb_score" in data["results"][0]


def test_search_empty_results(client):
    with patch("services.crawler.fetch_all", return_value=([], {})):
        response = client.get("/api/search?q=nonexistent")
        data = response.get_json()

    assert response.status_code == 200
    assert data["results"] == []
    assert data["sites"] == []


def test_crawler_caches_non_empty_results_only(monkeypatch):
    import services.crawler as crawler

    crawler.clear_cache()
    monkeypatch.setenv("RAPIDAPI_AMAZON_KEY", "test-key")
    monkeypatch.setattr(crawler.Config, "RAPIDAPI_AMAZON_KEY", "test-key")

    class FakeResponse:
        def __init__(self, products):
            self._products = products

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"products": self._products}}

    products = [{
        "product_price": "10",
        "product_title": "phone xyz",
        "product_star_rating": "4.5",
        "product_num_ratings": "100",
        "product_url": "https://example.com/p",
        "product_photo": "https://example.com/i.jpg",
    }]
    empty_products = []

    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(products)

    monkeypatch.setattr(crawler.requests, "get", fake_get)

    listings, counts = crawler.fetch_all("phone")
    assert len(listings) == 1
    assert listings[0]["site"] == "Amazon"
    assert counts == {"Amazon": 1, "AliExpress": 0, "eBay": 0}
    assert len(calls) == 1

    # Repeated query is served from cache: no upstream request.
    listings_again, counts_again = crawler.fetch_all("phone")
    assert listings_again == listings
    assert len(calls) == 1

    # A different query hits the upstream API again.
    crawler.fetch_all("tablet")
    assert len(calls) == 2

    # Empty results are not cached.
    def empty_get(*a, **k):
        calls.append(a[0] if a else "url")
        return FakeResponse(empty_products)
    monkeypatch.setattr(crawler.requests, "get", empty_get)
    assert crawler.fetch_all("nothing") == ([], {"Amazon": 0, "AliExpress": 0, "eBay": 0})
    assert crawler.fetch_all("nothing") == ([], {"Amazon": 0, "AliExpress": 0, "eBay": 0})
    assert len(calls) == 4
    crawler.clear_cache()
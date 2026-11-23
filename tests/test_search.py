from unittest.mock import patch

from app import create_app
from services import cache


def test_search_requires_query(client):
    response = client.get("/api/search")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_search_rejects_oversized_query(client):
    response = client.get("/api/search", query_string={"q": "x" * 256})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_search_preflight_allows_local_frontend(client):
    response = client.options(
        "/api/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "GET" in response.headers["Access-Control-Allow-Methods"]
    assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()


def test_cors_uses_app_config_override():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "CORS_ORIGINS": "https://shop.example",
    })
    response = app.test_client().get(
        "/api/health", headers={"Origin": "https://shop.example"}
    )
    assert response.headers["Access-Control-Allow-Origin"] == "https://shop.example"


def test_search_cache_uses_configured_ttl(monkeypatch):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SEARCH_CACHE_TTL_SECONDS": 5,
        "REDIS_URL": "",
    })
    now = [100.0]
    monkeypatch.setattr(cache.time, "time", lambda: now[0])
    cache.cache_clear()

    with app.app_context():
        cache.cache_set("ttl-test", {"listings": []})
        assert cache.cache_get("ttl-test") == {"listings": []}
        now[0] += 6
        assert cache.cache_get("ttl-test") is None


def test_search_cache_falls_back_when_redis_is_unavailable(monkeypatch):
    import redis

    cache_instance = cache.SearchCache()

    class UnavailableRedis:
        def get(self, key):
            raise redis.exceptions.ConnectionError("unavailable")

        def setex(self, key, ttl, value):
            raise redis.exceptions.ConnectionError("unavailable")

    monkeypatch.setattr(
        cache_instance,
        "_redis_client",
        lambda redis_url: (UnavailableRedis(), redis),
    )
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SEARCH_CACHE_TTL_SECONDS": 5,
        "REDIS_URL": "redis://unavailable",
    })

    with app.app_context():
        cache_instance.set("fallback", {"listings": []})
        assert cache_instance.get("fallback") == {"listings": []}


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
    monkeypatch.setattr(crawler.Config, "REDIS_URL", "")
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


def _listing(site, price=100):
    return {
        "site": site,
        "title": f"{site} item",
        "price": price,
        "rating": 4.0,
        "num_ratings": 0,
        "pay_on_delivery": False,
    }


def test_fetch_all_returns_fast_site_when_slow_site_times_out(monkeypatch):
    import time

    import services.crawler as crawler

    crawler.clear_cache()
    monkeypatch.setattr(crawler, "FETCH_ALL_TIMEOUT", 0.5)

    fast_calls = 0
    slow_calls = 0

    def fast(query):
        nonlocal fast_calls
        fast_calls += 1
        return [_listing("Fast")]

    def slow(query):
        nonlocal slow_calls
        slow_calls += 1
        time.sleep(2)
        return [_listing("Slow")]

    monkeypatch.setattr(crawler, "FETCHERS", {"Fast": fast, "Slow": slow})

    start = time.time()
    listings, counts = crawler.fetch_all("q")
    elapsed = time.time() - start

    assert elapsed < 1.5
    assert len(listings) == 1
    assert listings[0]["site"] == "Fast"
    assert counts == {"Fast": 1, "Slow": 0}

    # Not cached: second call re-invokes the fetchers.
    before = (fast_calls, slow_calls)
    crawler.fetch_all("q")
    assert (fast_calls, slow_calls) != before
    crawler.clear_cache()


def test_fetch_all_all_finish_in_time_are_cached(monkeypatch):
    import services.crawler as crawler

    crawler.clear_cache()
    monkeypatch.setattr(crawler, "FETCH_ALL_TIMEOUT", 0.5)

    calls = 0

    def fetcher(query):
        nonlocal calls
        calls += 1
        return [_listing("S")]

    monkeypatch.setattr(crawler, "FETCHERS", {"S": fetcher})

    listings, counts = crawler.fetch_all("q")
    assert len(listings) == 1
    assert counts == {"S": 1}

    # Cached: second call does not invoke the fetcher again.
    calls_before = calls
    listings_again, counts_again = crawler.fetch_all("q")
    assert listings_again == listings
    assert counts_again == counts
    assert calls == calls_before
    crawler.clear_cache()


def test_fetch_all_raiser_prevents_caching(monkeypatch):
    import services.crawler as crawler

    crawler.clear_cache()
    monkeypatch.setattr(crawler, "FETCH_ALL_TIMEOUT", 0.5)

    raiser_calls = 0
    ok_calls = 0

    def raiser(query):
        nonlocal raiser_calls
        raiser_calls += 1
        raise RuntimeError("boom")

    def ok(query):
        nonlocal ok_calls
        ok_calls += 1
        return [_listing("OK")]

    monkeypatch.setattr(crawler, "FETCHERS", {"Raiser": raiser, "OK": ok})

    listings, counts = crawler.fetch_all("q")
    assert len(listings) == 1
    assert listings[0]["site"] == "OK"
    assert counts == {"Raiser": 0, "OK": 1}

    # Not cached because Raiser raised: second call re-invokes the fetchers.
    before = (raiser_calls, ok_calls)
    crawler.fetch_all("q")
    assert (raiser_calls, ok_calls) != before
    crawler.clear_cache()
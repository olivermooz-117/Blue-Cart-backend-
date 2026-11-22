from unittest.mock import patch

VALID_LISTING = {
    "site": "Amazon",
    "title": "Phone",
    "price": 15000,
    "rating": 4.5,
    "num_ratings": 100,
    "pay_on_delivery": False,
    "url": "https://example.com",
    "image": "https://example.com/img.jpg",
}


def _post_filter(client, body):
    return client.post("/api/search/filter", json=body)


def test_filter_price_zero(client):
    response = _post_filter(client, {"listings": [{**VALID_LISTING, "price": 0}]})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_missing_price(client):
    listing = {**VALID_LISTING}
    del listing["price"]
    response = _post_filter(client, {"listings": [listing]})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_non_numeric_weights(client):
    response = _post_filter(
        client,
        {"listings": [VALID_LISTING], "weights": {"price": "high"}},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_listings_not_a_list(client):
    response = _post_filter(client, {"listings": "not-a-list"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_rejects_non_object_listing(client):
    response = _post_filter(client, {"listings": [None]})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_rejects_non_object_weights(client):
    response = _post_filter(client, {"listings": [VALID_LISTING], "weights": []})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_rejects_malformed_json(client):
    response = client.post(
        "/api/search/filter",
        data='{"listings":',
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_rejects_negative_num_ratings(client):
    response = _post_filter(
        client,
        {"listings": [{**VALID_LISTING, "num_ratings": -1}]},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_more_than_100_listings(client):
    response = _post_filter(
        client,
        {"listings": [{**VALID_LISTING, "title": f"item {i}"} for i in range(101)]},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_all_zero_weights(client):
    response = _post_filter(
        client,
        {"listings": [VALID_LISTING], "weights": {"price": 0, "rating": 0, "trust": 0}},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_filter_valid(client):
    with patch(
        "services.crawler.fetch_all", return_value=([], {})
    ):
        response = _post_filter(
            client,
            {"listings": [VALID_LISTING], "weights": {"price": 1, "rating": 1, "trust": 1}},
        )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["results"]) == 1
    assert "mb_score" in data["results"][0]
    assert "cb_score" in data["results"][0]

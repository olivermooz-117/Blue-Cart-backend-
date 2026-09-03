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

    with patch("services.crawler.fetch_all", return_value=mock_listings):
        response = client.get("/api/search?q=phone")
        data = response.get_json()

    assert response.status_code == 200
    assert data["query"] == "phone"
    assert "results" in data
    assert len(data["results"]) == 1
    assert "mb_score" in data["results"][0]
    assert "cb_score" in data["results"][0]


def test_search_empty_results(client):
    with patch("services.crawler.fetch_all", return_value=[]):
        response = client.get("/api/search?q=nonexistent")
        data = response.get_json()

    assert response.status_code == 200
    assert data["results"] == []
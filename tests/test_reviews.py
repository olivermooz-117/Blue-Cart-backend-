from unittest.mock import patch


def test_reviews_get_empty(client):
    response = client.get("/api/search/reviews?q=headphones")
    data = response.get_json()
    assert response.status_code == 200
    assert data["reviews"] == []


def test_reviews_get_requires_query(client):
    response = client.get("/api/search/reviews")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_reviews_create_success(client):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Great product!",
        "rating": 5,
    })
    data = response.get_json()
    assert response.status_code == 201
    assert data["query"] == "headphones"
    assert data["shop"] == "Amazon"
    assert data["author"] == "Alice"
    assert data["rating"] == 5


def test_reviews_create_missing_fields(client):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_reviews_create_invalid_rating(client):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Nice",
        "rating": 6,
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_reviews_create_rating_too_low(client):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Nice",
        "rating": 0,
    })
    assert response.status_code == 400


def test_reviews_create_guest_attaches_no_user(client):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Nice",
        "rating": 4,
    })
    data = response.get_json()
    assert response.status_code == 201
    assert "user_id" not in data
    assert data["author"] == "Alice"


def test_reviews_create_attaches_user_id(client, auth_headers):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "eBay",
        "author": "Bob",
        "comment": "Solid.",
        "rating": 3,
    }, headers=auth_headers)
    data = response.get_json()
    assert response.status_code == 201
    assert "user_id" not in data
    # author is the email local part, not the full email, and not the body value
    assert data["author"] == "test"


def test_reviews_get_returns_created(client):
    client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Great!",
        "rating": 5,
    })
    response = client.get("/api/search/reviews?q=headphones")
    data = response.get_json()
    assert response.status_code == 200
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["author"] == "Alice"
    assert data["reviews"][0]["rating"] == 5


def test_reviews_are_query_scoped(client):
    client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Great!",
        "rating": 5,
    })
    client.post("/api/search/reviews", json={
        "query": "laptop",
        "shop": "eBay",
        "author": "Bob",
        "comment": "Ok.",
        "rating": 3,
    })
    response = client.get("/api/search/reviews?q=headphones")
    data = response.get_json()
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["query"] == "headphones"


def test_reviews_ordered_newest_first(client):
    client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "First",
        "comment": "First review.",
        "rating": 4,
    })
    client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "eBay",
        "author": "Second",
        "comment": "Second review.",
        "rating": 5,
    })
    response = client.get("/api/search/reviews?q=headphones")
    data = response.get_json()
    assert data["reviews"][0]["author"] == "Second"
    assert data["reviews"][1]["author"] == "First"


def test_reviews_create_invalid_rating_non_numeric(client):
    response = client.post("/api/search/reviews", json={
        "query": "headphones",
        "shop": "Amazon",
        "author": "Alice",
        "comment": "Nice",
        "rating": "not-a-number",
    })
    assert response.status_code == 400
    assert "error" in response.get_json()

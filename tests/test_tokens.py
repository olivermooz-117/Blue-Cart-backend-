from datetime import timedelta
from unittest.mock import patch

from flask_jwt_extended import create_access_token


def _expired_token(app):
    with app.app_context():
        return create_access_token(identity="1", expires_delta=timedelta(seconds=-1))


def test_expired_token_on_history_is_401(client, app):
    token = _expired_token(app)
    response = client.get(
        "/api/history", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "token expired"}


def test_expired_token_on_search_is_guest(client, app):
    mock_listing = {
        "site": "Amazon",
        "title": "Phone",
        "price": 15000,
        "rating": 4.5,
        "num_ratings": 100,
        "pay_on_delivery": False,
        "url": "https://example.com",
        "image": "https://example.com/img.jpg",
    }
    with patch(
        "services.crawler.fetch_all",
        return_value=([mock_listing], {"Amazon": 1}),
    ):
        token = _expired_token(app)
        response = client.get(
            "/api/search?q=phone",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.get_json()["query"] == "phone"

    # The expired token is treated as a guest, so nothing is saved to
    # history for the (nonexistent) user it claimed to be.
    client.post("/api/auth/register", json={"email": "user@example.com", "password": "password123"})
    login = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    valid_token = login.get_json()["access_token"]
    response = client.get(
        "/api/history",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["history"] == []
    assert response.get_json()["total"] == 0


def test_malformed_token_on_search_is_guest(client):
    with patch("services.crawler.fetch_all", return_value=([], {})):
        response = client.get(
            "/api/search?q=phone",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
    assert response.status_code == 200
    assert response.get_json()["query"] == "phone"


def test_deleted_user_token_on_search_is_guest(client, app):
    with app.app_context():
        token = create_access_token(identity="999999")

    with patch("services.crawler.fetch_all", return_value=([], {})):
        response = client.get(
            "/api/search?q=phone",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.get_json()["query"] == "phone"


def test_malformed_identity_token_on_search_is_guest(client, app):
    with app.app_context():
        token = create_access_token(identity={"id": 1})

    with patch("services.crawler.fetch_all", return_value=([], {})):
        response = client.get(
            "/api/search?q=phone",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.get_json()["query"] == "phone"


def test_malformed_token_on_review_is_guest(client):
    response = client.post(
        "/api/search/reviews",
        json={
            "query": "phone",
            "shop": "Amazon",
            "author": "Guest",
            "comment": "Review",
            "rating": 4,
        },
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 201
    assert response.get_json()["author"] == "Guest"


def test_expired_token_on_review_is_guest(client, app):
    token = _expired_token(app)
    response = client.post(
        "/api/search/reviews",
        json={
            "query": "phone",
            "shop": "Amazon",
            "author": "Guest",
            "comment": "Review",
            "rating": 4,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.get_json()["author"] == "Guest"


def test_deleted_user_token_on_review_is_guest(client, app):
    with app.app_context():
        token = create_access_token(identity="999999")

    response = client.post(
        "/api/search/reviews",
        json={
            "query": "phone",
            "shop": "Amazon",
            "author": "Guest",
            "comment": "Review",
            "rating": 4,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.get_json()["author"] == "Guest"

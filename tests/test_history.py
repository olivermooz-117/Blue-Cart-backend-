from unittest.mock import patch

from extensions import db
from models import SearchHistory


def test_history_requires_auth(client):
    response = client.get("/api/history")
    assert response.status_code == 401


def test_history_empty_for_new_user(client, auth_headers):
    response = client.get("/api/history", headers=auth_headers)
    data = response.get_json()

    assert response.status_code == 200
    assert data["history"] == []
    assert data["total"] == 0


def test_history_records_search(client, auth_headers):
    # Perform a search while authenticated (this should save history)
    with patch("services.crawler.fetch_all", return_value=([], {})):
        client.get("/api/search?q=headphones", headers=auth_headers)

    response = client.get("/api/history", headers=auth_headers)
    data = response.get_json()

    assert response.status_code == 200
    assert len(data["history"]) == 1
    assert data["history"][0]["query"] == "headphones"
    assert data["total"] == 1


def test_history_limit_offset_total(client, auth_headers):
    # auth_headers registers user id 1
    with client.application.app_context():
        for i in range(7):
            db.session.add(SearchHistory(user_id=1, search_query=f"query {i}"))
        db.session.commit()

    response = client.get("/api/history?limit=3&offset=2", headers=auth_headers)
    data = response.get_json()
    assert response.status_code == 200
    assert data["total"] == 7
    assert len(data["history"]) == 3
    assert data["history"][0]["query"] == "query 4"
    assert data["history"][2]["query"] == "query 2"


def test_history_limit_clamped_to_max(client, auth_headers):
    response = client.get("/api/history?limit=999", headers=auth_headers)
    data = response.get_json()
    assert response.status_code == 200
    assert data["total"] == 0


def test_history_invalid_limit(client, auth_headers):
    response = client.get("/api/history?limit=abc", headers=auth_headers)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_history_invalid_offset(client, auth_headers):
    response = client.get("/api/history?offset=x", headers=auth_headers)
    assert response.status_code == 400
    assert "error" in response.get_json()

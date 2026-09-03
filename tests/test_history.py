from unittest.mock import patch
def test_history_requires_auth(client):
    response = client.get("/api/history")
    assert response.status_code == 401


def test_history_empty_for_new_user(client, auth_headers):
    response = client.get("/api/history", headers=auth_headers)
    data = response.get_json()

    assert response.status_code == 200
    assert data["history"] == []


def test_history_records_search(client, auth_headers):
    # Perform a search while authenticated (this should save history)
    with patch("services.crawler.fetch_all", return_value=[]):
        client.get("/api/search?q=headphones", headers=auth_headers)

    response = client.get("/api/history", headers=auth_headers)
    data = response.get_json()

    assert response.status_code == 200
    assert len(data["history"]) == 1
    assert data["history"][0]["query"] == "headphones"
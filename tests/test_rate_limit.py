from app import create_app
from extensions import db


def test_login_rate_limit_returns_429_json():
    app = create_app({
        "TESTING": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-jwt-secret",
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        db.create_all()
    client = app.test_client()

    for _ in range(10):
        response = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "wrong",
        })
        assert response.status_code == 401
        assert "error" in response.get_json()

    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "wrong",
    })
    assert response.status_code == 429
    assert response.get_json() == {"error": "Too Many Requests"}

import pytest
from app import create_app
from extensions import db


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-jwt-secret",
        "SECRET_KEY": "test-secret",
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123"
    })
    login = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    token = login.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
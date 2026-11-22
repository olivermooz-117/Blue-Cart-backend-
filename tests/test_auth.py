def test_register_success(client):
    response = client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "password": "password123"
    })
    data = response.get_json()

    assert response.status_code == 201
    assert "access_token" in data
    assert data["email"] == "newuser@example.com"


def test_register_missing_fields(client):
    response = client.post("/api/auth/register", json={
        "email": "incomplete@example.com"
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "password123"
    })
    response = client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "password123"
    })
    assert response.status_code == 409
    assert "already registered" in response.get_json()["error"]


def test_login_success(client):
    client.post("/api/auth/register", json={
        "email": "login@example.com",
        "password": "password123"
    })
    response = client.post("/api/auth/login", json={
        "email": "login@example.com",
        "password": "password123"
    })
    data = response.get_json()

    assert response.status_code == 200
    assert "access_token" in data
    assert data["email"] == "login@example.com"


def test_login_invalid_credentials(client):
    response = client.post("/api/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpass"
    })
    assert response.status_code == 401
    assert "error" in response.get_json()


def test_login_null_email(client):
    response = client.post("/api/auth/login", json={
        "email": None,
        "password": "password123"
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_login_null_password(client):
    response = client.post("/api/auth/login", json={
        "email": "wrong@example.com",
        "password": None
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_bad_email(client):
    response = client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "password123"
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_one_char_password(client):
    response = client.post("/api/auth/register", json={
        "email": "onechar@example.com",
        "password": "a"
    })
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_password_over_72_bytes(client):
    response = client.post("/api/auth/register", json={
        "email": "longpass@example.com",
        "password": "x" * 73
    })
    assert response.status_code == 400
    assert "error" in response.get_json()

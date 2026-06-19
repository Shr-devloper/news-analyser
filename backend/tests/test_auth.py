import uuid


def _email():
    return f"user-{uuid.uuid4().hex[:8]}@test.io"


def test_register_login_me(client):
    email = _email()
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret1", "full_name": "Test User"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == email

    r = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "supersecret1"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_login_wrong_password(client):
    email = _email()
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret1"},
    )
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "wrongpass"}
    )
    assert r.status_code == 401


def test_protected_requires_auth(client):
    r = client.get("/api/v1/reports")
    assert r.status_code == 401

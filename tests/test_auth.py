from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_success():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_user():
    response = client.post("/api/auth/login", json={"username": "nobody", "password": "admin"})
    assert response.status_code == 401


def test_chat_requires_token():
    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_chat_rejects_invalid_token():
    response = client.post(
        "/api/chat", json={"message": "hi"}, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401

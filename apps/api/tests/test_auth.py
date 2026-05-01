from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(database_path=tmp_path / "uninode-test.db"))


def test_register_login_and_me_round_trip(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "operator@example.test",
            "password": "correct horse battery staple",
            "display_name": "Ops Operator",
        },
    )

    assert register_response.status_code == 201
    registered = register_response.json()
    assert registered["user"]["email"] == "operator@example.test"
    assert registered["user"]["display_name"] == "Ops Operator"
    assert registered["token"]

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "operator@example.test",
            "password": "correct horse battery staple",
        },
    )

    assert login_response.status_code == 200
    token = login_response.json()["token"]

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "operator@example.test"


def test_login_rejects_wrong_password(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post(
        "/api/auth/register",
        json={
            "email": "operator@example.test",
            "password": "correct horse battery staple",
            "display_name": "Ops Operator",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "operator@example.test",
            "password": "wrong password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_register_rejects_duplicate_email(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = {
        "email": "operator@example.test",
        "password": "correct horse battery staple",
        "display_name": "Ops Operator",
    }

    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"

import pytest

from backend.app import create_app, db
from backend.auth import User


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret",
        "SQLALCHEMY_DATABASE_URI": (
            "sqlite:///" + (tmp_path / "auth-test.db").as_posix()
        ),
    })
    with app.test_client() as client:
        yield client


def register(client, email="customer@example.com"):
    return client.post("/api/auth/register", json={
        "email": email,
        "password": "SecurePassword2026!",
        "role": "staff",
    })


def test_registration(client):
    response = register(client)
    assert response.status_code == 201
    with client.application.app_context():
        user = db.session.query(User).filter_by(
            email="customer@example.com"
        ).first()
        assert user is not None
        assert user.role == "customer"
        assert user.password_hash != "SecurePassword2026!"


def test_duplicate_registration(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_short_password(client):
    response = client.post("/api/auth/register", json={
        "email": "short@example.com",
        "password": "short",
    })
    assert response.status_code == 400


def test_login_and_logout(client):
    register(client)

    response = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "SecurePassword2026!",
    })
    assert response.status_code == 200

    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_login(client):
    register(client)
    response = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "WrongPassword123!",
    })
    assert response.status_code == 401


def test_staff_access_restricted(client):
    register(client)
    client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "SecurePassword2026!",
    })
    assert client.get("/api/staff/check").status_code == 403


def test_staff_access_authorized(client):
    register(client)

    with client.application.app_context():
        user = db.session.query(User).filter_by(
            email="customer@example.com"
        ).first()
        user.role = "staff"
        db.session.commit()

    client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "SecurePassword2026!",
    })
    assert client.get("/api/staff/check").status_code == 200


def test_anonymous_access_denied(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/staff/check").status_code == 401


def test_invalid_json_registration(client):
    assert client.post(
        "/api/auth/register", data="invalid"
    ).status_code == 415

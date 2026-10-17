import pytest

from backend.app import create_app, db, ContactSubmission


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.db").as_posix(),
    })

    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_contact_submission(client):
    response = client.post("/api/contact", json={
        "name": "Test Customer",
        "email": "customer@example.com",
        "message": "Where is my robot?",
    })

    assert response.status_code == 201
    assert response.json["status"] == "received"

    app = client.application

    with app.app_context():
        saved = db.session.get(
            ContactSubmission,
            response.json["submission_id"],
        )
        assert saved is not None
        assert saved.email == "customer@example.com"


def test_invalid_email(client):
    response = client.post("/api/contact", json={
        "name": "Test",
        "email": "invalid",
        "message": "Hello",
    })
    assert response.status_code == 400


def test_empty_message(client):
    response = client.post("/api/contact", json={
        "name": "Test",
        "email": "test@example.com",
        "message": "",
    })
    assert response.status_code == 400


def test_non_json_request(client):
    response = client.post("/api/contact", data="hello")
    assert response.status_code == 415

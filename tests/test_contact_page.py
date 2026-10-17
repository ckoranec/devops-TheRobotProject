from backend.app import create_app


def test_contact_page_served():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/contact.html")

    assert response.status_code == 200
    assert b'id="contact-form"' in response.data
    assert b'action="/api/contact"' in response.data
    assert b'fetch("/api/contact"' in response.data


def test_home_page_served():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data

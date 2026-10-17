from backend.app import create_app


def test_contact_rate_limit(tmp_path):
    app = create_app({
        "TESTING": True,
        "RATELIMIT_ENABLED": True,
        "SQLALCHEMY_DATABASE_URI":
            "sqlite:///" + (tmp_path / "rate_limit.db").as_posix(),
    })

    payload = {
        "name": "Rate Limit Test",
        "email": "test@example.com",
        "message": "Testing request limits.",
    }

    with app.test_client() as client:
        for _ in range(5):
            response = client.post("/api/contact", json=payload)
            assert response.status_code == 201

        response = client.post("/api/contact", json=payload)
        assert response.status_code == 429

def test_public_backup_files_blocked():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        blocked = [
            "/MapAPI.html.before-leaflet.bak",
            "/contact.html.20261016-210815.bak",
            "/index.navigation-backup.html",
            "/example.zip",
            "/.env",
        ]

        for url in blocked:
            response = client.get(url)
            assert response.status_code == 404, (
                f"{url} returned {response.status_code}"
            )

        assert client.get("/contact.html").status_code == 200
        assert client.get("/MapAPI.html").status_code == 200

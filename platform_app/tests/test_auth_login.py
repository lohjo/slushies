import pytest

from app import bcrypt, create_app, db
from app.models import User


@pytest.fixture()
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app_ctx):
    return app_ctx.test_client()


def _seed_user(email="staff@example.com", password="secret123"):
    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(email=email, password=hashed, role="staff")
    db.session.add(user)
    db.session.commit()
    return user


def test_login_rejects_external_next_url(client):
    _seed_user()

    response = client.post(
        "/login?next=https://evil.example/phish",
        data={"email": "staff@example.com", "password": "secret123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_accepts_relative_next_url(client):
    _seed_user()

    response = client.post(
        "/login?next=/dashboard",
        data={"email": "staff@example.com", "password": "secret123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_unauthenticated_route_redirects_to_login(client):
    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

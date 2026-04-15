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


def test_public_signup_creates_staff_user_and_logs_in(client):
    response = client.post(
        "/signup",
        data={
            "name": "New User",
            "email": "new.user@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    user = User.query.filter_by(email="new.user@example.com").first()
    assert user is not None
    assert user.role == "staff"


def test_public_signup_rejects_duplicate_email_case_insensitive(client):
    _seed_user(email="staff@example.com", password="secret123")

    response = client.post(
        "/signup",
        data={
            "name": "Another Staff",
            "email": "STAFF@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert b"already exists" in response.data


def test_login_with_invalid_stored_hash_returns_200_not_500(client):
    user = User(email="legacy@example.com", password="not-a-bcrypt-hash", role="staff")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/login",
        data={"email": "legacy@example.com", "password": "secret123"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data

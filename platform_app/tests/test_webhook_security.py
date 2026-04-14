import pytest

from app import create_app, db
from app.models import User


@pytest.fixture()
def app_ctx(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app_ctx):
    return app_ctx.test_client()


def test_invalid_secret_returns_401(client, monkeypatch):
    monkeypatch.setattr("app.routes.webhook.process_row", lambda **kwargs: {"status": "pre_saved"})
    client.application.config["WEBHOOK_SECRET"] = "expected-secret"

    response = client.post(
        "/webhook/form-submit",
        json={"row_index": 2, "values": ["2026-04-01", "AB01", "pre"]},
        headers={"X-Webhook-Secret": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}


def test_prod_with_empty_secret_rejected(client, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr("app.routes.webhook.process_row", lambda **kwargs: {"status": "pre_saved"})
    client.application.config["WEBHOOK_SECRET"] = ""

    response = client.post(
        "/webhook/form-submit",
        json={"row_index": 2, "values": ["2026-04-01", "AB01", "pre"]},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}


def test_rate_limit_triggers_429_after_threshold(client, monkeypatch):
    monkeypatch.setattr("app.routes.webhook.process_row", lambda **kwargs: {"status": "pre_saved"})
    client.application.config["WEBHOOK_SECRET"] = "expected-secret"
    client.application.config["WEBHOOK_RATE_LIMIT"] = "2 per minute"

    headers = {"X-Webhook-Secret": "expected-secret"}
    payload = {"row_index": 2, "values": ["2026-04-01", "AB01", "pre"]}

    first = client.post("/webhook/form-submit", json=payload, headers=headers)
    second = client.post("/webhook/form-submit", json=payload, headers=headers)
    third = client.post("/webhook/form-submit", json=payload, headers=headers)

    assert first.status_code in (200, 202)
    assert second.status_code in (200, 202)
    assert third.status_code == 429


def test_dashboard_template_uses_local_widget_script_only(client):
    user = User(email="staff@example.com", password="hashed", role="staff")
    db.session.add(user)
    db.session.commit()

    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True

    response = client.get("/dashboard")

    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "dashboard_widget.js" in body
    assert "unpkg.com/react" not in body
    assert "unpkg.com/react-dom" not in body

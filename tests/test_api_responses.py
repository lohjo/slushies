import pytest

from app import create_app, db
from app.models import Participant, SurveyResponse, User


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


def _force_login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _seed_responses(count=5):
    user = User(email="staff@example.com", password="hashed", role="staff")
    participant = Participant(code="AB01", cohort="platform_apr_2026")
    db.session.add_all([user, participant])
    db.session.flush()

    responses = []
    for i in range(count):
        responses.append(
            SurveyResponse(
                participant_id=participant.id,
                survey_type="pre" if i % 2 == 0 else "post",
                sheet_row_index=100 + i,
                act_total=10 + i,
            )
        )

    db.session.add_all(responses)
    db.session.commit()
    return user


def test_list_responses_default_pagination(client):
    user = _seed_responses(count=3)
    _force_login(client, user.id)

    response = client.get("/api/responses")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["limit"] == 100
    assert payload["offset"] == 0
    assert payload["total"] == 3
    assert payload["returned"] == 3
    assert len(payload["items"]) == 3


def test_list_responses_respects_limit_and_offset(client):
    user = _seed_responses(count=5)
    _force_login(client, user.id)

    response = client.get("/api/responses?limit=2&offset=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert payload["total"] == 5
    assert payload["returned"] == 2
    assert [item["sheet_row_index"] for item in payload["items"]] == [101, 102]


def test_list_responses_rejects_non_integer_pagination(client):
    user = _seed_responses(count=2)
    _force_login(client, user.id)

    response = client.get("/api/responses?limit=abc&offset=0")

    assert response.status_code == 400
    assert "limit and offset" in response.get_json()["error"]

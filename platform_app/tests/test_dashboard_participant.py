import pytest

from app import create_app, db
from app.models import GrowthCard, Participant, SurveyResponse, User


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


def test_participant_page_renders_existing_participant(client):
    user = User(email="staff@example.com", password="hashed", role="staff")
    participant = Participant(code="AB01", cohort="platform_apr_2026")
    db.session.add_all([user, participant])
    db.session.flush()

    pre = SurveyResponse(
        participant_id=participant.id,
        survey_type="pre",
        sheet_row_index=2,
        act_total=15,
        cmi_total=10,
        rsem_total=18,
        ewb_total=16,
    )
    card = GrowthCard(participant_id=participant.id, delta_act=2.0)
    db.session.add_all([pre, card])
    db.session.commit()

    _force_login(client, user.id)
    response = client.get(f"/dashboard/participant/{participant.code}")

    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Participant AB01" in body
    assert "Pre Survey" in body
    assert "Growth Card" in body


def test_participant_page_missing_participant_returns_404(client):
    user = User(email="staff@example.com", password="hashed", role="staff")
    db.session.add(user)
    db.session.commit()

    _force_login(client, user.id)
    response = client.get("/dashboard/participant/UNKNOWN")

    assert response.status_code == 404

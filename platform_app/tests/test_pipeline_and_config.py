import csv

import pytest

from app import create_app, db
from app.config import ProductionConfig
from app.models import GrowthCard, Participant, SurveyResponse, User
from app.services.sheets_service import parse_row
from app.services.sync_service import process_row


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


def test_parse_row_partial_submission_is_safe():
    parsed = parse_row(["2026-04-02 09:00", "AB01", "pre", "4", "", "3"], row_index=2)

    assert parsed["sheet_row_index"] == 2
    assert parsed["act_a1"] == 4.0
    assert parsed["act_a2"] is None
    assert parsed["act_a3"] == 3.0
    assert parsed["reflect_e4"] is None


def test_process_row_missing_code_is_skipped(app_ctx):
    result = process_row(raw_row=["2026-04-02 09:00"], row_index=2)
    assert result["status"] == "skipped"


def test_process_row_invalid_row_index_is_skipped(app_ctx):
    result = process_row(raw_row=["2026-04-02 09:00", "AB01", "pre"], row_index=0)
    assert result == {"status": "skipped", "reason": "invalid row index"}


def test_process_row_deduplicates_same_sheet_row(app_ctx):
    row = ["2026-04-02 09:00", "AB01", "pre"]

    first = process_row(raw_row=row, row_index=2)
    second = process_row(raw_row=row, row_index=2)

    assert first["status"] == "pre_saved"
    assert second["status"] == "skipped"
    assert second["reason"] == "already processed"
    assert SurveyResponse.query.count() == 1


def test_export_csv_includes_delta_columns(app_ctx, client):
    admin = User(email="admin@example.com", password="hashed", role="admin")
    participant = Participant(code="AB01", cohort="platform_apr_2026")
    db.session.add_all([admin, participant])
    db.session.flush()

    response = SurveyResponse(
        participant_id=participant.id,
        survey_type="post",
        sheet_row_index=2,
        act_total=20,
        act_connect=7,
        act_act=6,
        act_thrive=7,
        cmi_total=14,
        rsem_total=22,
        ewb_total=19,
    )
    card = GrowthCard(
        participant_id=participant.id,
        delta_act=2.5,
        delta_cmi=1.5,
        delta_rsem=3.0,
        delta_ewb=2.0,
    )
    db.session.add_all([response, card])
    db.session.commit()

    _force_login(client, admin.id)
    export = client.get("/api/export/csv")

    assert export.status_code == 200

    rows = list(csv.DictReader(export.data.decode("utf-8").splitlines()))
    assert rows
    assert rows[0]["delta_act"] == "2.5"
    assert rows[0]["delta_cmi"] == "1.5"
    assert rows[0]["delta_rsem"] == "3.0"
    assert rows[0]["delta_ewb"] == "2.0"


def test_production_config_requires_database_url():
    original_uri = ProductionConfig.SQLALCHEMY_DATABASE_URI
    ProductionConfig.SQLALCHEMY_DATABASE_URI = None

    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            create_app("production")
    finally:
        ProductionConfig.SQLALCHEMY_DATABASE_URI = original_uri


def test_production_config_rewrites_postgres_scheme():
    original_uri = ProductionConfig.SQLALCHEMY_DATABASE_URI
    ProductionConfig.SQLALCHEMY_DATABASE_URI = "postgres://user:pass@localhost:5432/platform"

    try:
        app = create_app("production")
        assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql://")
    finally:
        ProductionConfig.SQLALCHEMY_DATABASE_URI = original_uri

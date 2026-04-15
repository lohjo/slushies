import csv
import sys
import types

import pytest
from unittest.mock import MagicMock

from app import create_app, db
from app.models import GrowthCard, Participant, SurveyResponse, User
from app.services.sheets_service import fetch_all_rows, parse_row
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


def test_process_row_backfills_partial_existing_row(app_ctx):
    partial_row = ["2026-04-02 09:00", "AB02", "pre", "4", "", "3"]
    complete_row = [
        "2026-04-02 09:00", "AB02", "pre", "25", "M",
        "4", "4", "4", "4", "4", "4",
        "3", "3", "3", "3", "3", "3",
        "3", "3", "3", "3", "3", "3", "3", "3", "3", "3",
        "4", "4", "4", "4", "4", "4",
    ]

    first = process_row(raw_row=partial_row, row_index=10)
    second = process_row(raw_row=complete_row, row_index=10)

    assert first["status"] == "pre_saved"
    assert second["status"] == "pre_backfilled"

    stored = SurveyResponse.query.filter_by(sheet_row_index=10).first()
    assert stored is not None
    assert stored.act_total is not None
    assert stored.cmi_total is not None
    assert stored.rsem_total is not None
    assert stored.ewb_total is not None


def test_post_card_failure_rolls_back_and_retry_succeeds(app_ctx, monkeypatch):
    pre_row = ["2026-04-02 09:00", "AB01", "pre", "4", "4", "4", "4", "4", "4"]
    post_row = ["2026-04-03 09:00", "AB01", "post", "5", "5", "5", "5", "5", "5"]

    assert process_row(raw_row=pre_row, row_index=2)["status"] == "pre_saved"

    failing_card_service = types.SimpleNamespace(
        generate_card=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("render failed"))
    )
    monkeypatch.setitem(sys.modules, "app.services.card_service", failing_card_service)

    failed = process_row(raw_row=post_row, row_index=3)
    assert failed["status"] == "failed"
    assert SurveyResponse.query.filter_by(sheet_row_index=3).first() is None

    success_card_service = types.SimpleNamespace(
        generate_card=lambda **kwargs: "instance/cards/retried.pdf"
    )
    monkeypatch.setitem(sys.modules, "app.services.card_service", success_card_service)

    retried = process_row(raw_row=post_row, row_index=3)
    assert retried["status"] == "card_generated"
    assert SurveyResponse.query.filter_by(sheet_row_index=3).first() is not None


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


def test_production_config_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URI", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app("production")


def test_production_config_rewrites_postgres_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/platform")
    app = create_app("production")
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql://")


def test_production_config_accepts_sqlalchemy_database_uri_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://user:pass@localhost:5432/platform",
    )
    app = create_app("production")
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "postgresql://user:pass@localhost:5432/platform"


def test_fetch_all_rows_uses_configured_range(app_ctx, monkeypatch):
    execute = MagicMock(return_value={"values": [["row"]]})
    get = MagicMock(return_value=MagicMock(execute=execute))
    values = MagicMock(get=get)
    spreadsheets = MagicMock(return_value=MagicMock(values=MagicMock(return_value=values)))
    fake_service = MagicMock(spreadsheets=spreadsheets)
    monkeypatch.setattr("app.services.sheets_service._get_service", lambda: fake_service)
    app_ctx.config["GOOGLE_SHEET_ID"] = "sheet-id"
    app_ctx.config["GOOGLE_SHEET_RANGE"] = "Responses!A2:AJ"

    rows = fetch_all_rows()

    assert rows == [["row"]]
    get.assert_called_once_with(spreadsheetId="sheet-id", range="Responses!A2:AJ")


def test_fetch_all_rows_raises_on_unexpected_empty(app_ctx, monkeypatch):
    execute = MagicMock(return_value={"values": []})
    get = MagicMock(return_value=MagicMock(execute=execute))
    values = MagicMock(get=get)
    spreadsheets = MagicMock(return_value=MagicMock(values=MagicMock(return_value=values)))
    fake_service = MagicMock(spreadsheets=spreadsheets)
    monkeypatch.setattr("app.services.sheets_service._get_service", lambda: fake_service)
    app_ctx.config["GOOGLE_SHEET_ID"] = "sheet-id"
    app_ctx.config["SHEETS_ALLOW_EMPTY"] = False

    with pytest.raises(RuntimeError, match="GOOGLE_SHEET_RANGE"):
        fetch_all_rows(sheet_range="Sheet1!A2:AJ")


def test_get_service_uses_json_env_when_present(app_ctx, monkeypatch):
    fake_credentials = MagicMock(name="creds")
    from_service_account_info = MagicMock(return_value=fake_credentials)
    monkeypatch.setattr(
        "app.services.sheets_service.service_account.Credentials.from_service_account_info",
        from_service_account_info,
    )
    monkeypatch.setattr(
        "app.services.sheets_service.build",
        MagicMock(return_value="fake-service"),
    )

    app_ctx.config["GOOGLE_SERVICE_ACCOUNT_JSON"] = '{"type":"service_account"}'

    from app.services.sheets_service import _get_service

    service = _get_service()
    assert service == "fake-service"
    from_service_account_info.assert_called_once()


def test_get_service_falls_back_to_file_when_env_missing(app_ctx, monkeypatch):
    fake_credentials = MagicMock(name="creds")
    from_service_account_file = MagicMock(return_value=fake_credentials)
    monkeypatch.setattr(
        "app.services.sheets_service.service_account.Credentials.from_service_account_file",
        from_service_account_file,
    )
    monkeypatch.setattr(
        "app.services.sheets_service.build",
        MagicMock(return_value="fake-service"),
    )

    app_ctx.config["GOOGLE_SERVICE_ACCOUNT_JSON"] = None
    app_ctx.config["GOOGLE_SERVICE_ACCOUNT_FILE"] = "service-account-key.json"

    from app.services.sheets_service import _get_service

    service = _get_service()
    assert service == "fake-service"
    from_service_account_file.assert_called_once_with("service-account-key.json", scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])


def test_get_service_invalid_json_env_raises_clear_error(app_ctx):
    app_ctx.config["GOOGLE_SERVICE_ACCOUNT_JSON"] = "{invalid-json"

    from app.services.sheets_service import _get_service

    with pytest.raises(RuntimeError, match="not valid JSON"):
        _get_service()

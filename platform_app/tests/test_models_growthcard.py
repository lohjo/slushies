import pytest
import types
import sys
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import GrowthCard, Participant
from app.services.sync_service import process_row


@pytest.fixture()
def app_ctx(monkeypatch):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        fake_card_service = types.SimpleNamespace(
            generate_card=lambda **kwargs: "instance/cards/fake-growth-card.pdf"
        )
        monkeypatch.setitem(sys.modules, "app.services.card_service", fake_card_service)
        yield app
        db.session.remove()
        db.drop_all()


def test_unique_participant_growthcard_enforced(app_ctx):
    participant = Participant(code="AB01", cohort="platform_apr_2026")
    db.session.add(participant)
    db.session.flush()

    first = GrowthCard(participant_id=participant.id, file_path="first.pdf", delta_act=1.0)
    db.session.add(first)
    db.session.commit()

    duplicate = GrowthCard(participant_id=participant.id, file_path="second.pdf", delta_act=2.0)
    db.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_sync_updates_existing_growthcard_instead_of_duplicate(app_ctx):
    pre_row = ["2026-04-02 09:00", "AB01", "pre", "4", "4", "4", "4", "4", "4"]
    post_row_a = ["2026-04-03 09:00", "AB01", "post", "5", "5", "5", "5", "5", "5"]
    post_row_b = ["2026-04-04 09:00", "AB01", "post", "3", "3", "3", "3", "3", "3"]

    assert process_row(raw_row=pre_row, row_index=2)["status"] == "pre_saved"

    first_post = process_row(raw_row=post_row_a, row_index=3)
    assert first_post["status"] == "card_generated"

    second_post = process_row(raw_row=post_row_b, row_index=4)
    assert second_post["status"] == "card_generated"

    participant = Participant.query.filter_by(code="AB01").first()
    cards = GrowthCard.query.filter_by(participant_id=participant.id).all()
    assert len(cards) == 1
    assert cards[0].file_path == "instance/cards/fake-growth-card.pdf"

from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager


# ─── User loader ──────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─── Users ────────────────────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    """Impart staff and admin accounts. NOT survey participants."""
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(128), nullable=False)   # bcrypt hash
    name       = db.Column(db.String(80))
    role       = db.Column(db.String(10), default="staff")   # 'admin' | 'staff'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active  = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role}


# ─── Participants ──────────────────────────────────────────────────────────────

class Participant(db.Model):
    """
    Anonymous participant record keyed on self-generated code
    (e.g. first 2 letters of mother's name + birth day).
    No PII is stored beyond the code.
    """
    __tablename__ = "participants"

    id         = db.Column(db.Integer, primary_key=True)
    code       = db.Column(db.String(20), unique=True, nullable=False, index=True)
    cohort     = db.Column(db.String(50))      # e.g. "platform_apr_2025"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    responses  = db.relationship("SurveyResponse", backref="participant", lazy=True)
    card       = db.relationship("GrowthCard", uselist=False, backref="participant")

    def to_dict(self):
        return {"id": self.id, "code": self.code, "cohort": self.cohort}


# ─── Survey Responses ─────────────────────────────────────────────────────────

class SurveyResponse(db.Model):
    """
    Stores one row per survey submission (pre or post).
    Raw item scores are stored alongside computed domain totals so
    we can re-score if rubrics change without re-fetching the sheet.
    """
    __tablename__ = "survey_responses"

    id               = db.Column(db.Integer, primary_key=True)
    participant_id   = db.Column(db.Integer, db.ForeignKey("participants.id"), nullable=False)
    survey_type      = db.Column(db.String(4), nullable=False)   # 'pre' | 'post'
    submitted_at     = db.Column(db.DateTime, default=datetime.utcnow)
    sheet_row_index  = db.Column(db.Integer, nullable=False, unique=True, index=True)
    # one physical row in the Google Sheet should map to one DB record only

    # ── ACT SG (A1–A6) — scored 1–5 each, total 6–30 ──
    act_a1 = db.Column(db.Float)   # I feel like I belong
    act_a2 = db.Column(db.Float)   # I have someone to go to
    act_a3 = db.Column(db.Float)   # I set goals
    act_a4 = db.Column(db.Float)   # I can find a way through
    act_a5 = db.Column(db.Float)   # Good direction in life
    act_a6 = db.Column(db.Float)   # Hopeful about future
    act_total  = db.Column(db.Float)   # sum A1–A6
    act_connect = db.Column(db.Float)  # A1+A2
    act_act     = db.Column(db.Float)  # A3+A4
    act_thrive  = db.Column(db.Float)  # A5+A6

    # ── CMI (B1–B6) — scored 1–4 each, total 6–24 ──
    cmi_b1 = db.Column(db.Float)
    cmi_b2 = db.Column(db.Float)
    cmi_b3 = db.Column(db.Float)
    cmi_b4 = db.Column(db.Float)
    cmi_b5 = db.Column(db.Float)
    cmi_b6 = db.Column(db.Float)
    cmi_total = db.Column(db.Float)

    # ── Rosenberg Self-Esteem (C1–C10) — reverse-scored, total 0–30 ──
    rsem_c1  = db.Column(db.Float)
    rsem_c2  = db.Column(db.Float)   # reverse
    rsem_c3  = db.Column(db.Float)
    rsem_c4  = db.Column(db.Float)
    rsem_c5  = db.Column(db.Float)   # reverse
    rsem_c6  = db.Column(db.Float)   # reverse
    rsem_c7  = db.Column(db.Float)
    rsem_c8  = db.Column(db.Float)   # reverse
    rsem_c9  = db.Column(db.Float)   # reverse
    rsem_c10 = db.Column(db.Float)
    rsem_total = db.Column(db.Float)

    # ── Eudaimonic Well-Being (D1–D6) — scored 1–5 each, total 6–30 ──
    ewb_d1 = db.Column(db.Float)
    ewb_d2 = db.Column(db.Float)
    ewb_d3 = db.Column(db.Float)
    ewb_d4 = db.Column(db.Float)
    ewb_d5 = db.Column(db.Float)
    ewb_d6 = db.Column(db.Float)
    ewb_total = db.Column(db.Float)

    # ── Open reflection (post only) ──
    reflect_e1 = db.Column(db.Text)
    reflect_e2 = db.Column(db.Text)
    reflect_e3 = db.Column(db.Text)
    reflect_e4 = db.Column(db.Text)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# ─── Growth Cards ─────────────────────────────────────────────────────────────

class GrowthCard(db.Model):
    """Stores metadata about a generated growth card."""
    __tablename__ = "growth_cards"

    id             = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participants.id"), nullable=False, unique=True)
    generated_at   = db.Column(db.DateTime, default=datetime.utcnow)
    file_path      = db.Column(db.String(255))   # local path to PDF/PNG
    drive_url      = db.Column(db.String(500))   # optional Google Drive link
    emailed        = db.Column(db.Boolean, default=False)

    # Snapshot of change scores at time of generation
    delta_act  = db.Column(db.Float)
    delta_cmi  = db.Column(db.Float)
    delta_rsem = db.Column(db.Float)
    delta_ewb  = db.Column(db.Float)
    cohens_d   = db.Column(db.Float)   # overall effect size

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
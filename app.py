from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

#SQLite for dev
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///platform.db"

#Swap to Postgres for production
# app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:pass@localhost/platform"

db = SQLAlchemy(app)

# Define the SurveyResponse model
class SurveyResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    participant = db.Column(db.String(20), nullable=False)
    survey_type = db.Column(db.String(4), nullable=False)
    act_total = db.Column(db.Float)
    cmi_total = db.Column(db.Float)
    rsem_total = db.Column(db.Float)
    ewb_total = db.Column(db.Float)
    submitted_at = db.Column(db.DateTime, default=db.func.now())


@app.route("/responses/<code>", methods=["GET"])
def get_responses(code):
    rows = SurveyResponse.query.filter_by(participant=code).all()
    return jsonify([r.to_dict() for r in rows])

# UPDATE
@app.route("/responses/<int:id>", methods=["PUT"])
def update_response(id):
    entry = SurveyResponse.query.get_or_404(id)
    for key, val in request.json.items():
        setattr(entry, key, val)
    db.session.commit()
    return jsonify(entry.to_dict())

# DELETE
@app.route("/responses/<int:id>", methods=["DELETE"])
def delete_response(id):
    entry = SurveyResponse.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'deleted': id})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
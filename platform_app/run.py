import os
import click
from app import create_app, db
from app.models import User, Participant, SurveyResponse, GrowthCard

app = create_app(os.getenv("FLASK_ENV", "development"))


# ─── CLI commands ─────────────────────────────────────────────────────────────

@app.cli.command("init-db")
def init_db():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        click.echo("Database initialised.")


@app.cli.command("create-admin")
@click.option("--email",    prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--name",     default="Admin")
def create_admin(email, password, name):
    """Seed the first admin user."""
    from app import bcrypt
    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(email=email, password=hashed, name=name, role="admin")
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin user {email} created.")


@app.cli.command("sync")
def sync():
    """Manually pull all rows from Google Sheets."""
    from app.services.sync_service import sync_all_from_sheets
    results = sync_all_from_sheets()
    for r in results:
        click.echo(r)


if __name__ == "__main__":
    app.run()
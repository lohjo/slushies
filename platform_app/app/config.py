import os
import warnings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "instance"))
DEV_DB_PATH = os.path.join(INSTANCE_DIR, "platform_dev.db").replace("\\", "/")
DEFAULT_SECRET_KEY = "7b81f6c88cf963e6549676f3d3e0a8fe-platform-change-in-production"


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
    GOOGLE_SHEET_RANGE = os.getenv("GOOGLE_SHEET_RANGE", "Sheet1!A2:AJ")
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "service-account-key.json"
    )
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    CARDS_OUTPUT_DIR = os.path.join(BASE_DIR, "..", "instance", "cards")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
    WEBHOOK_RATE_LIMIT = os.getenv("WEBHOOK_RATE_LIMIT", "30 per minute")
    SHEETS_ALLOW_EMPTY = os.getenv("SHEETS_ALLOW_EMPTY", "false").lower() == "true"

    @staticmethod
    def init_app(app):
        """Hook for config-specific runtime validation."""
        return None


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DEV_DATABASE_URL",
        f"sqlite:///{DEV_DB_PATH}",
    )

    @staticmethod
    def init_app(app):
        uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
        prefix = "sqlite:///"
        if uri.startswith(prefix):
            db_path = uri[len(prefix):]
            if db_path and not os.path.isabs(db_path):
                db_path = os.path.abspath(os.path.join(BASE_DIR, "..", db_path))
                app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.replace('\\', '/')}"

        os.makedirs(INSTANCE_DIR, exist_ok=True)


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = None

    @staticmethod
    def init_app(app):
        uri = os.getenv("DATABASE_URL")
        if not uri:
            raise RuntimeError("DATABASE_URL must be set when FLASK_ENV=production.")

        # Heroku/Render supply postgres:// but SQLAlchemy needs postgresql://
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = uri

        if app.config.get("SECRET_KEY") == DEFAULT_SECRET_KEY:
            warnings.warn(
                "SECRET_KEY is using the default value in production.",
                RuntimeWarning,
                stacklevel=2,
            )


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
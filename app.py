import logging
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from config import Config
from extensions import bcrypt, db, jwt
from flask_migrate import Migrate
from routes.auth import auth_bp
from routes.history import history_bp
from routes.reviews import reviews_bp
from routes.search import search_bp
from validation import ApiError

migrate = Migrate()

logger = logging.getLogger(__name__)


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_overrides:
        app.config.update(config_overrides)

    CORS(app)
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(search_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(reviews_bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({"error": err.message}), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify({"error": err.name or "error"}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        logger.exception("Unhandled error: %s", err)
        return jsonify({"error": "internal server error"}), 500

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    @app.cli.command("init-db")
    def init_db():
        """Create all tables directly (local/dev convenience). Prefer
        `flask db upgrade` for managed schema migrations."""
        db.create_all()
        print("Database tables created via db.create_all().")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

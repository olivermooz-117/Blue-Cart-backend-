import logging
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from extensions import bcrypt, db, jwt, limiter
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

    # Rate limiting is disabled under TESTING unless a test enables it.
    app.config.setdefault("RATELIMIT_ENABLED", not app.config.get("TESTING", False))

    # Trust Render's proxy for the real client IP (rate limiting, logs).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    allowed_origins = [
        origin.strip()
        for origin in app.config.get("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if "http://localhost:5173" not in allowed_origins:
        allowed_origins.append("http://localhost:5173")
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": allowed_origins,
                "allow_headers": ["Authorization", "Content-Type"],
            }
        },
    )
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    @jwt.expired_token_loader
    def _expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "token expired"}), 401

    @jwt.invalid_token_loader
    def _invalid_token_callback(reason):
        return jsonify({"error": "invalid token"}), 401

    @jwt.unauthorized_loader
    def _unauthorized_callback(reason):
        return jsonify({"error": "authorization required"}), 401

    @jwt.revoked_token_loader
    def _revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "token revoked"}), 401

    @jwt.needs_fresh_token_loader
    def _needs_fresh_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "fresh token required"}), 401

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

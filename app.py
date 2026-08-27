from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import bcrypt, db, jwt
from routes.auth import auth_bp
from routes.history import history_bp
from routes.search import search_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(search_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    @app.cli.command("init-db")
    def init_db():
        """Create all tables: `flask --app app init-db`."""
        db.create_all()
        print("Database tables created.")

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)

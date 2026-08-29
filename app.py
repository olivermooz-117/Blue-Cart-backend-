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

    # Register blueprints - search_bp already has /api prefix
    app.register_blueprint(search_bp)  # Routes: /api/search, /api/search/filter
    app.register_blueprint(auth_bp)    # Routes: /api/auth/...
    app.register_blueprint(history_bp) # Routes: /api/history/...

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        print("Database tables created.")

    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

from app import create_app
from extensions import db
from sqlalchemy import inspect


def test_database_migrations_start_from_empty_database(tmp_path):
    database_path = tmp_path / "migration-test.db"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "JWT_SECRET_KEY": "test-jwt-secret",
        "SECRET_KEY": "test-secret",
    })

    result = app.test_cli_runner().invoke(args=["db", "upgrade"])

    assert result.exit_code == 0, result.output
    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())
    assert {"users", "search_history", "reviews", "alembic_version"} <= tables

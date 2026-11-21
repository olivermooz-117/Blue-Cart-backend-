from datetime import datetime, timezone

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    searches = db.relationship("SearchHistory", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)
    preferences = db.relationship(
        "UserPreference", backref="user", lazy=True, uselist=False
    )


class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    search_query = db.Column(db.String(255), nullable=False)
    searched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    # Stored in DB column `query`; Python attribute `search_query` avoids
    # shadowing SQLAlchemy's Model.query property.
    search_query = db.Column("query", db.String(255), nullable=False, index=True)
    shop = db.Column(db.String(120), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.search_query,
            "shop": self.shop,
            "author": self.author,
            "comment": self.comment,
            "rating": self.rating,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SearchCache(db.Model):
    """In-DB cache of search results keyed by normalized query."""

    __tablename__ = "search_cache"

    query = db.Column(db.String(255), primary_key=True)
    results = db.Column(db.JSON, nullable=False)
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)


class UserPreference(db.Model):
    """Logged-in user's saved ranking preferences."""

    __tablename__ = "user_preferences"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    default_weights = db.Column(db.JSON, nullable=False, default=dict)
    preferred_shops = db.Column(db.JSON, nullable=False, default=list)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

from datetime import datetime, timezone

from extensions import db


def utc_now():
    """Callable default: current UTC time, timezone-aware."""
    return datetime.now(timezone.utc)


def _iso_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    searches = db.relationship("SearchHistory", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)


class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    search_query = db.Column(db.String(255), nullable=False)
    searched_at = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.Index("ix_search_history_user_searched", "user_id", "searched_at"),
    )


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    # Stored in DB column `query`; Python attribute `search_query` avoids
    # shadowing SQLAlchemy's Model.query property.
    search_query = db.Column("query", db.String(255), nullable=False)
    query_key = db.Column(db.String(255), nullable=False, index=True)
    shop = db.Column(db.String(50), nullable=False)
    author = db.Column(db.String(50), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="chk_reviews_rating"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.search_query,
            "shop": self.shop,
            "author": self.author,
            "comment": self.comment,
            "rating": self.rating,
            "created_at": _iso_utc(self.created_at),
        }

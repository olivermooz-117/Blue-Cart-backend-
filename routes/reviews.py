from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db, limiter
from models import Review

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/search")

MIN_RATING = 1
MAX_RATING = 5


def _optional_user_id():
    """Return the JWT identity if a valid token was sent, else None (guest)."""
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        return int(identity) if identity is not None else None
    except Exception:
        return None


@reviews_bp.route("/reviews", methods=["GET"])
def get_reviews():
    """Return reviews for a search query, newest first."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    reviews = (
        Review.query.filter_by(search_query=query)
        .order_by(Review.created_at.desc())
        .all()
    )
    return jsonify({"reviews": [r.to_dict() for r in reviews]})


@reviews_bp.route("/reviews", methods=["POST"])
@limiter.limit("5/minute")
def create_review():
    """Create a review for a shop/product under a search query.

    No login required; a valid JWT attaches the reviewer's user_id.
    """
    body = request.get_json(force=True) or {}

    query = body.get("query", "").strip()
    shop = body.get("shop", "").strip()
    author = body.get("author", "").strip()
    comment = body.get("comment", "").strip()
    rating = body.get("rating")

    if not query or not shop or not author or not comment:
        return jsonify({"error": "query, shop, author and comment are required"}), 400

    try:
        rating = float(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be a number between 1 and 5"}), 400

    if rating < MIN_RATING or rating > MAX_RATING:
        return jsonify(
            {"error": f"rating must be between {MIN_RATING} and {MAX_RATING}"}
        ), 400

    user_id = _optional_user_id()

    review = Review(
        search_query=query,
        shop=shop,
        author=author,
        comment=comment,
        rating=rating,
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(review)
    db.session.commit()

    return jsonify(review.to_dict()), 201

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db, limiter
from models import Review, User, utc_now
from validation import ApiError, clean_str, get_json_object

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/search")

MIN_RATING = 1
MAX_RATING = 5


def _current_user():
    """Return (user_id, email_local_part) for a valid token, else (None, None)."""
    try:
        from flask_jwt_extended.exceptions import JWTExtendedException

        import jwt

        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        user_id = int(identity) if identity is not None else None
    except (JWTExtendedException, jwt.exceptions.PyJWTError, ValueError):
        return None, None
    if user_id is None:
        return None, None
    user = db.session.get(User, user_id)
    if user is None:
        return None, None
    return user_id, user.email.split("@", 1)[0]


@reviews_bp.route("/reviews", methods=["GET"])
def get_reviews():
    """Return reviews for a search query, newest first."""
    query = request.args.get("q")
    if not query or not query.strip():
        raise ApiError("Query parameter 'q' is required", 400)

    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        raise ApiError("limit must be an integer", 400)
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        raise ApiError("offset must be an integer", 400)
    limit = max(0, min(limit, 100))
    offset = max(0, offset)

    reviews = (
        Review.query.filter_by(query_key=query.strip().lower())
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify({"reviews": [r.to_dict() for r in reviews]})


@reviews_bp.route("/reviews", methods=["POST"])
@limiter.limit("5/minute")
def create_review():
    """Create a review for a shop/product under a search query.

    No login required; a valid JWT attaches the reviewer's user_id and sets
    the author to the user's email local part (full emails are never
    exposed publicly).
    """
    body = get_json_object()

    query = clean_str(body.get("query"), "query", 255)
    shop = clean_str(body.get("shop"), "shop", 50)
    comment = clean_str(body.get("comment"), "comment", 1000)

    rating = body.get("rating")
    if (
        isinstance(rating, bool)
        or not isinstance(rating, int)
        or rating < MIN_RATING
        or rating > MAX_RATING
    ):
        raise ApiError("rating must be an integer between 1 and 5", 400)

    user_id, author = _current_user()
    if author is None:
        author = clean_str(body.get("author"), "author", 50)

    review = Review(
        search_query=query,
        query_key=query.strip().lower(),
        shop=shop,
        author=author,
        comment=comment,
        rating=rating,
        user_id=user_id,
        created_at=utc_now(),
    )
    db.session.add(review)
    db.session.commit()

    return jsonify(review.to_dict()), 201

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from extensions import db
from models import SearchHistory
from services import crawler, mb_cb

search_bp = Blueprint("search", __name__, url_prefix="/api/search")


@search_bp.route("", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    listings = crawler.fetch_all(query)
    ranked = mb_cb.rank_listings(listings)

    user_id = _optional_user_id()
    if user_id:
        db.session.add(SearchHistory(user_id=user_id, search_query=query))
        db.session.commit()

    return jsonify({"query": query, "results": ranked})


@search_bp.route("/filter", methods=["POST"])
def filter_search():
    """Re-rank a set of listings the client already has using custom weights."""
    body = request.get_json(force=True) or {}
    listings = body.get("listings", [])
    weights = body.get("weights", {})

    ranked = mb_cb.rank_listings(listings, weights)
    return jsonify({"results": ranked})


def _optional_user_id():
    """Return the JWT identity if a valid token was sent, else None (guest search)."""
    try:
        from flask_jwt_extended import verify_jwt_in_request

        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        return int(identity) if identity is not None else None
    except Exception:
        return None

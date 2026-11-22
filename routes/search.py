from math import isfinite

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from extensions import db
from models import SearchHistory
from services import cache, crawler, mb_cb
from services.mb_cb import DEFAULT_WEIGHTS
from validation import ApiError, get_json_object

search_bp = Blueprint("search", __name__, url_prefix="/api/search")


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


@search_bp.route("", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    if not query:
        raise ApiError("Query parameter 'q' is required", 400)

    ip = _client_ip()
    if not cache.rate_limit_allowed(ip):
        return jsonify({"error": "Too many requests. Please try again later."}), 429

    cached = cache.cache_get(query)
    if cached is not None:
        return jsonify({"query": query, "results": cached, "cached": True})

    listings, site_counts = crawler.fetch_all(query)
    ranked = mb_cb.rank_listings(listings)

    cache.cache_set(query, ranked)

    user_id = _optional_user_id()
    if user_id:
        db.session.add(SearchHistory(user_id=user_id, search_query=query))
        db.session.commit()

    sites = [site for site, count in site_counts.items() if count > 0]
    return jsonify({"query": query, "results": ranked, "sites": sites, "cached": False})


@search_bp.route("/filter", methods=["POST"])
def filter_search():
    """Re-rank a set of listings the client already has using custom weights."""
    body = get_json_object()

    listings = body.get("listings", [])
    if not isinstance(listings, list):
        raise ApiError("listings must be a list", 400)
    if len(listings) > 100:
        raise ApiError("listings must contain at most 100 items", 400)

    for index, listing in enumerate(listings):
        if not isinstance(listing, dict):
            raise ApiError(f"listings[{index}] must be an object", 400)
        prefix = f"listings[{index}]"

        price = listing.get("price")
        if (
            not isinstance(price, (int, float))
            or isinstance(price, bool)
            or not isfinite(price)
            or price <= 0
        ):
            raise ApiError(f"{prefix}.price must be a positive number", 400)

        rating = listing.get("rating", 0)
        if (
            not isinstance(rating, (int, float))
            or isinstance(rating, bool)
            or not isfinite(rating)
            or not (0 <= rating <= 5)
        ):
            raise ApiError(f"{prefix}.rating must be between 0 and 5", 400)

        num_ratings = listing.get("num_ratings", 0)
        if (
            not isinstance(num_ratings, int)
            or isinstance(num_ratings, bool)
            or num_ratings < 0
        ):
            raise ApiError(
                f"{prefix}.num_ratings must be a non-negative integer", 400
            )

        pay_on_delivery = listing.get("pay_on_delivery", False)
        if not isinstance(pay_on_delivery, bool):
            raise ApiError(f"{prefix}.pay_on_delivery must be a boolean", 400)

        site = listing.get("site")
        if not isinstance(site, str):
            raise ApiError(f"{prefix}.site must be a string", 400)

    weights = body.get("weights", {})
    if not isinstance(weights, dict):
        raise ApiError("weights must be an object", 400)

    supplied = {
        key: value
        for key, value in weights.items()
        if key in ("price", "rating", "trust")
    }
    for key, value in supplied.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not isfinite(value)
            or value < 0
        ):
            raise ApiError(f"weights.{key} must be a number >= 0", 400)
    if supplied and all(value == 0 for value in supplied.values()):
        raise ApiError("weights: at least one supplied weight must be > 0", 400)

    cleaned_weights = {**DEFAULT_WEIGHTS, **supplied}

    ranked = mb_cb.rank_listings(listings, cleaned_weights)
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

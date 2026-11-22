from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import SearchHistory, _iso_utc
from validation import ApiError

history_bp = Blueprint("history", __name__, url_prefix="/api/history")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@history_bp.route("", methods=["GET"])
@jwt_required()
def get_history():
    user_id = int(get_jwt_identity())

    try:
        limit = int(request.args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        raise ApiError("limit must be an integer", 400)
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        raise ApiError("offset must be an integer", 400)
    limit = max(0, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    base = SearchHistory.query.filter_by(user_id=user_id)
    total = base.count()
    entries = (
        base.order_by(SearchHistory.searched_at.desc(), SearchHistory.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify({
        "history": [
            {"query": e.search_query, "searched_at": _iso_utc(e.searched_at)}
            for e in entries
        ],
        "total": total,
    })

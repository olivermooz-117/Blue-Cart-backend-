from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import SearchHistory

history_bp = Blueprint("history", __name__, url_prefix="/api/history")


@history_bp.route("", methods=["GET"])
@jwt_required()
def get_history():
    user_id = int(get_jwt_identity())
    entries = (
        SearchHistory.query.filter_by(user_id=user_id)
        .order_by(SearchHistory.searched_at.desc())
        .all()
    )
    return jsonify(
        {
            "history": [
                {"query": e.search_query, "searched_at": e.searched_at.isoformat()}
                for e in entries
            ]
        }
    )

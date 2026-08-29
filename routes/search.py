from flask import Blueprint, jsonify, request

# Simple blueprint for testing
search_bp = Blueprint("search", __name__, url_prefix="/api")

@search_bp.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    return jsonify({
        "query": query,
        "message": "Search endpoint is working!",
        "results": [
            {"id": 1, "name": f"Test product for {query}", "price": 100}
        ]
    })

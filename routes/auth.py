from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError

from extensions import bcrypt, db, limiter
from models import User
from validation import ApiError, clean_str, EMAIL_REGEX, get_json_object

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Precomputed hash of a dummy password so login performs a bcrypt check
# even when the email is unknown, evening out timing between existing and
# unknown accounts.
_DUMMY_PASSWORD_HASH = bcrypt.generate_password_hash("x" * 40).decode("utf-8")


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10/minute")
def register():
    body = get_json_object()

    email = clean_str(body.get("email"), "email", 120)
    if not EMAIL_REGEX.match(email):
        raise ApiError("email must be a valid email address", 400)

    password = body.get("password")
    if not isinstance(password, str):
        raise ApiError("password must be a string", 400)
    password_bytes = password.encode("utf-8")
    if not (8 <= len(password_bytes) <= 72):
        raise ApiError("password must be between 8 and 72 bytes", 400)

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(email=email, password_hash=password_hash)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("email already registered", 409)

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "email": user.email}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10/minute")
def login():
    body = get_json_object()

    email = body.get("email")
    password = body.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise ApiError("email and password must be strings", 400)

    user = User.query.filter_by(email=email.strip().lower()).first()

    if user:
        ok = bcrypt.check_password_hash(user.password_hash, password)
    else:
        ok = bcrypt.check_password_hash(_DUMMY_PASSWORD_HASH, password)

    if not ok:
        return jsonify({"error": "invalid email or password"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "email": user.email})

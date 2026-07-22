from functools import wraps

from flask import Blueprint, jsonify, request, session

from .models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


def _get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return db.session.get(User, user_id)


@auth_bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "an account with this email already exists"}), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session.clear()
    session["user_id"] = user.id
    return jsonify(user.to_dict()), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid email or password"}), 401

    session.clear()
    session["user_id"] = user.id
    return jsonify(user.to_dict()), 200


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True}), 200


@auth_bp.get("/me")
@login_required
def me():
    user = _get_current_user()
    if user is None:
        session.clear()
        return jsonify({"error": "authentication required"}), 401
    return jsonify(user.to_dict()), 200

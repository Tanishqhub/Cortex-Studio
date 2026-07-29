"""Marketplace API (Phase 5): a shared, browsable catalogue of successful
build artifacts.

Visibility model: an Artifact is private by default -- visible only to the
user who owns the build that produced it. A user can mark their own
artifact public, at which point it becomes browsable and downloadable by
any logged-in user via the "public" scope. The "mine" scope always shows
every artifact the caller owns, public or not. See docs/DECISIONS.md
Phase 5 for the full reasoning.
"""

from flask import Blueprint, Response, current_app, jsonify, request

from .auth import current_user_id, login_required
from .models import Artifact, Build, db
from .storage import LocalStorage

marketplace_bp = Blueprint("marketplace", __name__, url_prefix="/api")


def _storage():
    return LocalStorage(current_app.config["UPLOAD_FOLDER"])


@marketplace_bp.get("/marketplace")
@login_required
def list_marketplace():
    viewer_id = current_user_id()
    scope = request.args.get("scope", "public")

    query = Artifact.query.join(Build)
    if scope == "mine":
        query = query.filter(Build.user_id == viewer_id)
    else:
        query = query.filter(Artifact.is_public.is_(True))

    artifacts = query.order_by(Artifact.created_at.desc()).all()
    return jsonify([a.to_dict(viewer_id=viewer_id) for a in artifacts]), 200


@marketplace_bp.get("/artifacts/<int:artifact_id>")
@login_required
def get_artifact(artifact_id):
    viewer_id = current_user_id()
    artifact = db.session.get(Artifact, artifact_id)
    if artifact is None:
        return jsonify({"error": "artifact not found"}), 404
    if not artifact.is_public and artifact.build.user_id != viewer_id:
        return jsonify({"error": "artifact not found"}), 404
    return jsonify(artifact.to_dict(include_log=True, viewer_id=viewer_id)), 200


@marketplace_bp.patch("/artifacts/<int:artifact_id>/visibility")
@login_required
def set_artifact_visibility(artifact_id):
    viewer_id = current_user_id()
    artifact = db.session.get(Artifact, artifact_id)
    if artifact is None:
        return jsonify({"error": "artifact not found"}), 404
    if artifact.build.user_id != viewer_id:
        return jsonify({"error": "only the owner can change visibility"}), 403

    data = request.get_json(silent=True) or {}
    if "is_public" not in data or not isinstance(data["is_public"], bool):
        return jsonify({"error": "is_public (boolean) is required"}), 400

    artifact.is_public = data["is_public"]
    db.session.commit()
    return jsonify(artifact.to_dict(viewer_id=viewer_id)), 200


@marketplace_bp.get("/artifacts/<int:artifact_id>/download")
@login_required
def download_artifact(artifact_id):
    viewer_id = current_user_id()
    artifact = db.session.get(Artifact, artifact_id)
    if artifact is None:
        return jsonify({"error": "artifact not found"}), 404
    if not artifact.is_public and artifact.build.user_id != viewer_id:
        return jsonify({"error": "artifact not found"}), 404

    try:
        data = _storage().read_bytes(artifact.download_ref)
    except OSError:
        return jsonify({"error": "stored binary is missing"}), 404

    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )

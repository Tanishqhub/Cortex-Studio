"""Marketplace API (Phase 5): a shared, browsable catalogue of successful
build artifacts.

Visibility model: every Artifact is browsable and downloadable by any
logged-in user, regardless of who owns the workspace it came from. This is
the simplest of the three options the phase brief explicitly allows
("interpret the visibility/sharing model as you see fit") and matches the
brief's own language -- a "shared, browsable catalogue" -- more directly
than an owner-only or split browse/download model would. See
docs/DECISIONS.md Phase 5 for the full reasoning and rejected alternatives.
"""

from flask import Blueprint, Response, current_app, jsonify

from .auth import login_required
from .models import Artifact, db
from .storage import LocalStorage

marketplace_bp = Blueprint("marketplace", __name__, url_prefix="/api")


def _storage():
    return LocalStorage(current_app.config["UPLOAD_FOLDER"])


@marketplace_bp.get("/marketplace")
@login_required
def list_marketplace():
    artifacts = Artifact.query.order_by(Artifact.created_at.desc()).all()
    return jsonify([a.to_dict() for a in artifacts]), 200


@marketplace_bp.get("/artifacts/<int:artifact_id>")
@login_required
def get_artifact(artifact_id):
    artifact = db.session.get(Artifact, artifact_id)
    if artifact is None:
        return jsonify({"error": "artifact not found"}), 404
    return jsonify(artifact.to_dict(include_log=True)), 200


@marketplace_bp.get("/artifacts/<int:artifact_id>/download")
@login_required
def download_artifact(artifact_id):
    artifact = db.session.get(Artifact, artifact_id)
    if artifact is None:
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

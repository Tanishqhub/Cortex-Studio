import json
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session

from .a2l_parser import ParseError, parse_a2l
from .auth import login_required
from .models import A2LFile, Workspace, db
from .storage import LocalStorage

workspaces_bp = Blueprint("workspaces", __name__, url_prefix="/api/workspaces")

ALLOWED_A2L_EXTENSION = ".a2l"


def _storage():
    return LocalStorage(current_app.config["UPLOAD_FOLDER"])


def _get_owned_workspace(workspace_id):
    """Returns the workspace only if it exists AND belongs to the current
    user. Callers must 404 (not 403) on None to avoid leaking existence of
    other users' workspaces — see phase2 spec / DECISIONS.md."""
    workspace = db.session.get(Workspace, workspace_id)
    if workspace is None or workspace.owner_id != session["user_id"]:
        return None
    return workspace


@workspaces_bp.post("")
@login_required
def create_workspace():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    workspace = Workspace(name=name, owner_id=session["user_id"])
    db.session.add(workspace)
    db.session.commit()
    return jsonify(workspace.to_dict()), 201


@workspaces_bp.get("")
@login_required
def list_workspaces():
    workspaces = (
        Workspace.query.filter_by(owner_id=session["user_id"]).order_by(Workspace.created_at.desc()).all()
    )
    return jsonify([w.to_dict() for w in workspaces]), 200


@workspaces_bp.get("/<int:workspace_id>")
@login_required
def get_workspace(workspace_id):
    workspace = _get_owned_workspace(workspace_id)
    if workspace is None:
        return jsonify({"error": "workspace not found"}), 404

    result = workspace.to_dict()
    if workspace.a2l_file is not None:
        result["a2l_file"] = workspace.a2l_file.to_dict()
    return jsonify(result), 200


@workspaces_bp.delete("/<int:workspace_id>")
@login_required
def delete_workspace(workspace_id):
    workspace = _get_owned_workspace(workspace_id)
    if workspace is None:
        return jsonify({"error": "workspace not found"}), 404

    if workspace.a2l_file is not None:
        _storage().delete(workspace.a2l_file.stored_path)

    db.session.delete(workspace)
    db.session.commit()
    return jsonify({"ok": True}), 200


@workspaces_bp.post("/<int:workspace_id>/a2l")
@login_required
def upload_a2l(workspace_id):
    workspace = _get_owned_workspace(workspace_id)
    if workspace is None:
        return jsonify({"error": "workspace not found"}), 404

    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify({"error": "no file provided (expected multipart field 'file')"}), 400

    if not file.filename.lower().endswith(ALLOWED_A2L_EXTENSION):
        return jsonify({"error": f"only {ALLOWED_A2L_EXTENSION} files are accepted"}), 400

    raw_bytes = file.read()
    max_size = current_app.config["MAX_A2L_SIZE_BYTES"]
    if len(raw_bytes) > max_size:
        return jsonify({"error": f"file exceeds the {max_size // (1024 * 1024)} MB size limit"}), 400

    text = raw_bytes.decode("utf-8", errors="replace")

    try:
        parsed = parse_a2l(text)
    except ParseError as exc:
        return jsonify({"error": str(exc)}), 422

    relative_path = f"workspace_{workspace.id}/source.a2l"
    _storage().write_bytes(relative_path, raw_bytes)

    signals_json = json.dumps(
        {"measurements": parsed["measurements"], "characteristics": parsed["characteristics"]}
    )
    summary_json = json.dumps(parsed["summary"])

    a2l_file = workspace.a2l_file
    if a2l_file is None:
        a2l_file = A2LFile(
            workspace_id=workspace.id,
            filename=file.filename,
            stored_path=relative_path,
            signals_json=signals_json,
            summary_json=summary_json,
        )
        db.session.add(a2l_file)
    else:
        a2l_file.filename = file.filename
        a2l_file.stored_path = relative_path
        a2l_file.uploaded_at = datetime.now(timezone.utc)
        a2l_file.signals_json = signals_json
        a2l_file.summary_json = summary_json

    db.session.commit()

    return jsonify({"filename": a2l_file.filename, "summary": parsed["summary"]}), 201


@workspaces_bp.get("/<int:workspace_id>/signals")
@login_required
def get_signals(workspace_id):
    workspace = _get_owned_workspace(workspace_id)
    if workspace is None:
        return jsonify({"error": "workspace not found"}), 404

    a2l_file = workspace.a2l_file
    if a2l_file is None:
        return jsonify({"error": "no A2L file uploaded for this workspace yet"}), 404

    signals = json.loads(a2l_file.signals_json)
    summary = json.loads(a2l_file.summary_json)
    return (
        jsonify(
            {
                "measurements": signals["measurements"],
                "characteristics": signals["characteristics"],
                "summary": summary,
            }
        ),
        200,
    )

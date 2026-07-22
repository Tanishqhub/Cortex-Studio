"""Build trigger + status API. Builds run in a bounded worker pool
(ThreadPoolExecutor) so a burst of requests queues rather than spawning
unbounded sandbox containers -- see docs/SECURITY.md T8.

Streaming vs. polling: this implements the polling fallback the phase brief
explicitly allows ("Acceptable simpler fallback: poll GET /api/builds/<id>
for status + full log"). compiler.run_build() only returns once the
container has finished (gcc runs sub-second for realistic inputs), so there
is no partial output to stream mid-build anyway -- see docs/DECISIONS.md.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, current_app, jsonify, session

from .compiler import run_build
from .auth import login_required
from .models import Build, Workspace, db
from .storage import LocalStorage
from .workspaces import _get_owned_workspace

builds_bp = Blueprint("builds", __name__, url_prefix="/api")

BUILD_WORKER_COUNT = int(os.environ.get("BUILD_WORKER_COUNT", 2))
_executor = ThreadPoolExecutor(max_workers=BUILD_WORKER_COUNT, thread_name_prefix="build-worker")


def _run_build_job(app, build_id):
    """Runs in a worker-pool thread, outside any request context -- needs
    its own app context to touch the DB / config."""
    with app.app_context():
        build = db.session.get(Build, build_id)
        if build is None:
            return

        build.status = "running"
        db.session.commit()

        workspace = db.session.get(Workspace, build.workspace_id)
        source_code = workspace.source_code or ""
        measurements = []
        if workspace.a2l_file is not None:
            measurements = json.loads(workspace.a2l_file.signals_json)["measurements"]

        result = run_build(source_code, measurements)

        build = db.session.get(Build, build_id)
        build.status = result["status"]
        build.exit_code = result["exit_code"]
        build.log_text = result["log_text"]
        build.duration_ms = result["duration_ms"]

        storage = LocalStorage(app.config["UPLOAD_FOLDER"])
        if result["elf_bytes"] is not None:
            elf_ref = f"workspace_{build.workspace_id}/builds/{build.id}/out.elf"
            storage.write_bytes(elf_ref, result["elf_bytes"])
            build.artifact_ref = elf_ref
        if result["bin_bytes"] is not None:
            bin_ref = f"workspace_{build.workspace_id}/builds/{build.id}/out.bin"
            storage.write_bytes(bin_ref, result["bin_bytes"])
            build.bin_artifact_ref = bin_ref

        db.session.commit()


@builds_bp.post("/workspaces/<int:workspace_id>/builds")
@login_required
def trigger_build(workspace_id):
    workspace = _get_owned_workspace(workspace_id)
    if workspace is None:
        return jsonify({"error": "workspace not found"}), 404

    if not workspace.source_code or not workspace.source_code.strip():
        return jsonify({"error": "workspace has no source code to compile"}), 400

    # Simple per-user rate limit: at most one outstanding (queued/running)
    # build per user at a time. Chosen over a token-bucket/sliding-window
    # limiter for simplicity at this scale -- see docs/DECISIONS.md.
    outstanding = (
        Build.query.filter_by(user_id=session["user_id"]).filter(Build.status.in_(["queued", "running"])).count()
    )
    if outstanding > 0:
        return (
            jsonify({"error": "you already have a build queued or running; wait for it to finish"}),
            429,
        )

    build = Build(workspace_id=workspace.id, user_id=session["user_id"], status="queued")
    db.session.add(build)
    db.session.commit()

    app = current_app._get_current_object()
    _executor.submit(_run_build_job, app, build.id)

    return jsonify(build.to_dict(include_log=False)), 201


@builds_bp.get("/builds/<int:build_id>")
@login_required
def get_build(build_id):
    build = db.session.get(Build, build_id)
    if build is None or build.user_id != session["user_id"]:
        return jsonify({"error": "build not found"}), 404
    return jsonify(build.to_dict()), 200


@builds_bp.get("/workspaces/<int:workspace_id>/builds")
@login_required
def list_builds(workspace_id):
    workspace = _get_owned_workspace(workspace_id)
    if workspace is None:
        return jsonify({"error": "workspace not found"}), 404

    builds = Build.query.filter_by(workspace_id=workspace.id).order_by(Build.created_at.desc()).limit(20).all()
    return jsonify([b.to_dict(include_log=False) for b in builds]), 200

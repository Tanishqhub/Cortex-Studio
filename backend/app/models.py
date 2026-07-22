from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "email": self.email}


class Workspace(db.Model):
    __tablename__ = "workspaces"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    source_code = db.Column(db.Text, nullable=True)

    a2l_file = db.relationship(
        "A2LFile", uselist=False, back_populates="workspace", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "has_a2l_file": self.a2l_file is not None,
        }


class A2LFile(db.Model):
    """One A2L file per workspace; raw file lives in storage (see storage.py),
    parsed signals + summary are cached here as JSON so /signals doesn't
    re-parse on every request."""

    __tablename__ = "a2l_files"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, unique=True, index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    signals_json = db.Column(db.Text, nullable=False)
    summary_json = db.Column(db.Text, nullable=False)

    workspace = db.relationship("Workspace", back_populates="a2l_file")

    def to_dict(self):
        return {
            "filename": self.filename,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class Build(db.Model):
    """One compile attempt of a workspace's source. See
    backend/app/compiler.py (the sandboxed build runner) and
    backend/app/builds.py (the API + worker pool).

    status transitions: queued -> running -> (success | error). A row is
    created (status=queued) synchronously on POST so the client always gets
    a build id back immediately; the worker pool thread updates it as the
    build progresses.
    """

    __tablename__ = "builds"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="queued")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    duration_ms = db.Column(db.Integer, nullable=True)
    exit_code = db.Column(db.Integer, nullable=True)
    log_text = db.Column(db.Text, nullable=True)
    # Storage-relative path to the linked ELF (with debug info). Phase 5's
    # Artifact model is the one users download from; this is Phase 4's own
    # record that a build produced *something*, kept simple per this
    # phase's model spec (single nullable artifact_ref).
    artifact_ref = db.Column(db.String(500), nullable=True)
    # objcopy -O binary output alongside the ELF -- both are cheap to keep
    # (see docs/DECISIONS.md, Phase 4) since the reference build command
    # explicitly produces both and Phase 5 needs a raw binary to serve.
    bin_artifact_ref = db.Column(db.String(500), nullable=True)

    workspace = db.relationship("Workspace")
    user = db.relationship("User")

    def to_dict(self, include_log=True):
        result = {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "has_artifact": self.artifact_ref is not None,
        }
        if include_log:
            result["log_text"] = self.log_text
        return result

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

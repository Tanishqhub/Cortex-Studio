import io
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENV"] = "testing"

import pytest

from app import create_app
from app.config import Config
from app.models import db

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "_resources", "Reference_a2l.a2l")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture
def app(tmp_path):
    TestConfig.UPLOAD_FOLDER = str(tmp_path / "uploads")
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _signup(client, email):
    resp = client.post("/api/auth/signup", json={"email": email, "password": "supersecret1"})
    assert resp.status_code == 201


def _sample_bytes():
    with open(SAMPLE_PATH, "rb") as f:
        return f.read()


def test_create_and_list_workspace(client):
    _signup(client, "alice@example.com")
    resp = client.post("/api/workspaces", json={"name": "My ECU project"})
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "My ECU project"

    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_upload_sample_and_get_signals(client):
    _signup(client, "alice@example.com")
    workspace_id = client.post("/api/workspaces", json={"name": "ws"}).get_json()["id"]

    resp = client.post(
        f"/api/workspaces/{workspace_id}/a2l",
        data={"file": (io.BytesIO(_sample_bytes()), "Reference_a2l.a2l")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["summary"]["measurement_count"] == 173

    resp = client.get(f"/api/workspaces/{workspace_id}/signals")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["summary"]["measurement_count"] == 173
    assert body["summary"]["characteristic_count"] == 0
    gear = next(m for m in body["measurements"] if m["name"] == "current_gear")
    assert gear["datatype"] == "UBYTE"
    assert gear["address"] == "0x280058C0"
    assert gear["limits"] == {"lower": 0, "upper": 2}


def test_reject_non_a2l_extension(client):
    _signup(client, "alice@example.com")
    workspace_id = client.post("/api/workspaces", json={"name": "ws"}).get_json()["id"]

    resp = client.post(
        f"/api/workspaces/{workspace_id}/a2l",
        data={"file": (io.BytesIO(b"not an a2l file"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_cross_user_workspace_access_is_404(client):
    _signup(client, "alice@example.com")
    workspace_id = client.post("/api/workspaces", json={"name": "alice's ws"}).get_json()["id"]
    client.post("/api/auth/logout")

    _signup(client, "bob@example.com")
    resp = client.get(f"/api/workspaces/{workspace_id}")
    assert resp.status_code == 404

    resp = client.get(f"/api/workspaces/{workspace_id}/signals")
    assert resp.status_code == 404

    resp = client.post(
        f"/api/workspaces/{workspace_id}/a2l",
        data={"file": (io.BytesIO(_sample_bytes()), "Reference_a2l.a2l")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404

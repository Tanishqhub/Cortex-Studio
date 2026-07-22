import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENV"] = "testing"

import pytest

from app import create_app
from app.config import Config
from app.models import db


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
    client.post("/api/auth/signup", json={"email": email, "password": "supersecret1"})


def _build_and_wait(client, workspace_id):
    resp = client.post(f"/api/workspaces/{workspace_id}/builds")
    assert resp.status_code == 201
    build_id = resp.get_json()["id"]

    body = None
    for _ in range(30):
        body = client.get(f"/api/builds/{build_id}").get_json()
        if body["status"] in ("success", "error"):
            break
        time.sleep(0.5)
    return build_id, body


def test_successful_build_appears_in_marketplace_with_required_metadata(client):
    """Real podman compile (same as test_builds_api) -- this phase's point is
    verifying a real artifact lands in the marketplace, not a mocked one."""
    _signup(client, "alice@example.com")
    ws = client.post("/api/workspaces", json={"name": "alice-ws"}).get_json()
    client.put(f"/api/workspaces/{ws['id']}/source", json={"code": "int main(void) { return 0; }"})

    build_id, build_body = _build_and_wait(client, ws["id"])
    assert build_body["status"] == "success", build_body

    listing = client.get("/api/marketplace").get_json()
    assert len(listing) == 1
    entry = listing[0]
    assert entry["build_id"] == build_id
    assert entry["workspace_id"] == ws["id"]
    assert entry["workspace_name"] == "alice-ws"
    assert entry["user_email"] == "alice@example.com"
    assert entry["size_bytes"] > 0
    assert entry["duration_ms"] is not None
    assert entry["created_at"] is not None
    assert entry["build_created_at"] is not None
    assert "log_text" not in entry  # list view omits the full log

    detail = client.get(f"/api/artifacts/{entry['id']}").get_json()
    assert detail["log_text"] == build_body["log_text"]


def test_marketplace_visible_to_any_logged_in_user_not_just_owner(client):
    """Visibility model (docs/DECISIONS.md Phase 5): every artifact is
    browsable/downloadable by any logged-in user, not just its owner."""
    _signup(client, "alice@example.com")
    ws = client.post("/api/workspaces", json={"name": "alice-ws"}).get_json()
    client.put(f"/api/workspaces/{ws['id']}/source", json={"code": "int main(void) { return 0; }"})
    _, build_body = _build_and_wait(client, ws["id"])
    assert build_body["status"] == "success", build_body

    client.post("/api/auth/logout")
    _signup(client, "bob@example.com")

    listing = client.get("/api/marketplace").get_json()
    assert len(listing) == 1
    assert listing[0]["user_email"] == "alice@example.com"


def test_download_returns_real_binary_bytes(client):
    _signup(client, "alice@example.com")
    ws = client.post("/api/workspaces", json={"name": "alice-ws"}).get_json()
    client.put(f"/api/workspaces/{ws['id']}/source", json={"code": "int main(void) { return 0; }"})
    _, build_body = _build_and_wait(client, ws["id"])
    assert build_body["status"] == "success", build_body

    entry = client.get("/api/marketplace").get_json()[0]

    resp = client.get(f"/api/artifacts/{entry['id']}/download")
    assert resp.status_code == 200
    assert resp.mimetype == "application/octet-stream"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert entry["filename"] in resp.headers["Content-Disposition"]
    assert len(resp.data) == entry["size_bytes"]
    assert len(resp.data) > 0


def test_marketplace_and_download_require_login(client):
    resp = client.get("/api/marketplace")
    assert resp.status_code == 401

    resp = client.get("/api/artifacts/1")
    assert resp.status_code == 401

    resp = client.get("/api/artifacts/1/download")
    assert resp.status_code == 401


def test_unknown_artifact_404s(client):
    _signup(client, "alice@example.com")
    assert client.get("/api/artifacts/999").status_code == 404
    assert client.get("/api/artifacts/999/download").status_code == 404


def test_failed_build_does_not_create_an_artifact(client):
    _signup(client, "alice@example.com")
    ws = client.post("/api/workspaces", json={"name": "broken-ws"}).get_json()
    client.put(f"/api/workspaces/{ws['id']}/source", json={"code": "int main(void) { int x = ; return 0; }"})

    _, build_body = _build_and_wait(client, ws["id"])
    assert build_body["status"] == "error", build_body

    listing = client.get("/api/marketplace").get_json()
    assert listing == []

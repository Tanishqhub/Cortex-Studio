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


def _signup_and_create_workspace(client, email="alice@example.com"):
    client.post("/api/auth/signup", json={"email": email, "password": "supersecret1"})
    ws = client.post("/api/workspaces", json={"name": "ws"}).get_json()
    client.put(f"/api/workspaces/{ws['id']}/source", json={"code": "int main(void) { return 0; }"})
    return ws["id"]


def test_trigger_build_runs_end_to_end_via_real_sandbox(client):
    """Uses the real podman sandbox (same as production) -- slower than a
    unit test, but this phase's whole point is verifying the real thing
    compiles, not a mocked stand-in."""
    workspace_id = _signup_and_create_workspace(client)

    resp = client.post(f"/api/workspaces/{workspace_id}/builds")
    assert resp.status_code == 201
    build_id = resp.get_json()["id"]
    assert resp.get_json()["status"] == "queued"

    status = None
    for _ in range(30):
        body = client.get(f"/api/builds/{build_id}").get_json()
        status = body["status"]
        if status in ("success", "error"):
            break
        time.sleep(0.5)

    assert status == "success", body
    assert body["exit_code"] == 0
    assert body["has_artifact"] is True
    assert body["duration_ms"] is not None


def test_build_requires_owner(client):
    workspace_id = _signup_and_create_workspace(client, "alice@example.com")
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "bob@example.com", "password": "supersecret1"})

    resp = client.post(f"/api/workspaces/{workspace_id}/builds")
    assert resp.status_code == 404


def test_rate_limit_rejects_second_build_while_one_outstanding(client, monkeypatch):
    """Decouples this assertion from real compile timing (see
    docs/DECISIONS.md): patches the compile step to block briefly so the
    first build is still queued/running when the second request lands,
    without depending on a race against a real ~1s podman compile."""
    import threading

    release = threading.Event()

    def slow_fake_run_build(source_code, measurements):
        release.wait(timeout=5)
        return {
            "status": "success",
            "exit_code": 0,
            "log_text": "",
            "duration_ms": 1,
            "elf_bytes": b"fake",
            "bin_bytes": b"fake",
        }

    monkeypatch.setattr("app.builds.run_build", slow_fake_run_build)

    workspace_id = _signup_and_create_workspace(client)

    first = client.post(f"/api/workspaces/{workspace_id}/builds")
    assert first.status_code == 201

    second = client.post(f"/api/workspaces/{workspace_id}/builds")
    assert second.status_code == 429

    release.set()

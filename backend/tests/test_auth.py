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


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_signup_success(client):
    resp = client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "bob@example.com"


def test_signup_duplicate_email_rejected(client):
    client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    resp = client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "anotherpass1"},
    )
    assert resp.status_code == 409


def test_login_wrong_password_401(client):
    client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    client.post("/api/auth/logout")
    resp = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "wrongpass1"},
    )
    assert resp.status_code == 401


def test_me_requires_session(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401

    client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "bob@example.com"

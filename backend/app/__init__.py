import os

from flask import Flask, jsonify, send_from_directory
from flask_migrate import Migrate

from .auth import auth_bp, login_required
from .builds import builds_bp
from .config import Config
from .marketplace import marketplace_bp
from .models import db
from .workspaces import workspaces_bp

migrate = Migrate()

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist")


def create_app(config_class=Config):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(auth_bp)
    app.register_blueprint(workspaces_bp)
    app.register_blueprint(builds_bp)
    app.register_blueprint(marketplace_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/protected-example")
    @login_required
    def protected_example():
        return jsonify({"ok": True})

    dist_dir = os.path.abspath(FRONTEND_DIST)

    @app.get("/")
    @app.get("/<path:path>")
    def serve_spa(path=""):
        if path and os.path.isfile(os.path.join(dist_dir, path)):
            return send_from_directory(dist_dir, path)
        index_path = os.path.join(dist_dir, "index.html")
        if not os.path.isfile(index_path):
            return jsonify({"error": "frontend build not found; run `npm run build` in frontend/"}), 404
        return send_from_directory(dist_dir, "index.html")

    return app

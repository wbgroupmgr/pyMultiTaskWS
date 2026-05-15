"""
trackerWeb/app.py
=================
Minimal reference-implementation Tracker for testing the MultiTrack
Web Platform dispatcher.

Mount point: /web
Home page  : /web/  (requires login)
Auth       : /web/login  /web/logout  /web/register
"""

import os
import platform
import secrets
from pathlib import Path

import flask
from flask import Flask, render_template, session

from multitrack.auth import ALLOWED_ROLES, make_auth_routes

_HERE = Path(__file__).resolve().parent

VERSION = "0.1.0"


class TrackerWebApp:
    def __init__(self, db_path: Path, tracker_name: str = "TrackerWeb"):
        self.tracker_name = tracker_name
        self.db_path      = db_path

        self.app = Flask(
            __name__,
            template_folder=str(_HERE / "templates"),
        )
        self.app.secret_key = os.environ.get("WEB_SECRET_KEY", secrets.token_hex(32))

        make_auth_routes(
            self.app,
            db_path=db_path,
            tracker_name=tracker_name,
            allowed_roles=ALLOWED_ROLES,
        )

        @self.app.context_processor
        def _inject():
            return {
                "current_user": session.get("username", ""),
                "current_role": session.get("role", ""),
                "tracker_name": tracker_name,
                "version":      VERSION,
            }

        self._bind_routes()

    def _bind_routes(self):
        app          = self.app
        tracker_name = self.tracker_name

        @app.route("/")
        def home():
            return render_template(
                "home.html",
                python_version=platform.python_version(),
                flask_version=flask.__version__,
                db_path=str(self.db_path),
            )

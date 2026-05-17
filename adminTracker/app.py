"""
adminTracker/app.py
===================
Platform administration Tracker for MultiTrack Web Platform.

Mount point: /admin
Home page  : /admin/  (requires login — shows all registered tracker apps)
Auth       : /admin/login  /admin/logout  /admin/register
"""

import os
import platform
import secrets
import signal
from pathlib import Path

import flask
from flask import Flask, jsonify, render_template, session

from multitrack.auth import ALLOWED_ROLES, make_auth_routes

_HERE = Path(__file__).resolve().parent

VERSION = "0.1.0"


class AdminTrackerApp:
    def __init__(self, db_path: Path, trackers: list = None, tracker_name: str = "AdminTracker"):
        self.tracker_name = tracker_name
        self.db_path      = db_path
        self.trackers     = trackers or []

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
        app      = self.app
        trackers = self.trackers

        @app.route("/")
        def home():
            return render_template(
                "home.html",
                python_version=platform.python_version(),
                flask_version=flask.__version__,
                db_path=str(self.db_path),
                trackers=trackers,
            )

        @app.route("/stop", methods=["POST"])
        def stop_web():
            # FIXME: Before killing, async-notify each registered Tracker that the
            # server is going down in 2 minutes so they can log users off gracefully.
            #
            # Design sketch:
            #   from adminTracker import registry
            #   import threading, time, requests
            #
            #   def _notify_and_kill():
            #       for t in registry.TRACKERS:
            #           shutdown_url = t.get("url", "").rstrip("/") + "/notify/shutdown"
            #           try:
            #               requests.post(shutdown_url, json={"countdown": 120}, timeout=2)
            #           except Exception:
            #               pass   # best-effort; don't block the shutdown
            #       time.sleep(120)
            #       os.kill(os.getpid(), signal.SIGTERM)
            #
            #   threading.Thread(target=_notify_and_kill, daemon=True).start()
            #   return jsonify({"status": "shutdown_scheduled", "countdown": 120})
            #
            # Each Tracker must implement POST /<tracker>/notify/shutdown and
            # broadcast a "server going down" banner to active sessions.
            os.kill(os.getpid(), signal.SIGTERM)
            return ("", 204)

"""
trackerWeb/wsgi.py — WSGI entry point for the TrackerWeb Tracker.

Standalone (local test, no dispatcher):
    MULTITRACK_GPG_PASSPHRASE=test1234567890 python trackerWeb/wsgi.py

Via DispatcherMiddleware (multitrack_wsgi.py):
    Mount point: /web
    Exposes:     application
"""

import os
import sys
from pathlib import Path

# pyMultiTaskWS/ root → makes both `multitrack` and `trackerWeb` importable
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from multitrack.auth import ALLOWED_ROLES, find_user, hash_password, load_users, save_users
from trackerWeb.app import TrackerWebApp

_DB_PATH = Path(__file__).resolve().parent / "Accts" / "pw.json.gpg"

# ── Auto-seed: create default user on first run so no separate setup is needed
def _ensure_db():
    pp = os.environ.get("MULTITRACK_GPG_PASSPHRASE", "")
    if not pp:
        return
    try:
        users = load_users(_DB_PATH) if _DB_PATH.exists() else []
        if not find_user(users, "webadmin"):
            from datetime import datetime
            users.append({
                "username":   "webadmin",
                "password":   hash_password("WebAdmin0!"),
                "full_name":  "TrackerWeb Admin",
                "phone":      "",
                "role":       "member",
                "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            })
            save_users(_DB_PATH, users)
    except Exception:
        pass  # server still starts; login will show "service unavailable"

_ensure_db()

_app_obj   = TrackerWebApp(db_path=_DB_PATH, tracker_name="TrackerWeb")
application = _app_obj.app

if __name__ == "__main__":
    # Run standalone without the dispatcher (useful for local smoke-test)
    print("Starting TrackerWeb standalone on http://127.0.0.1:5001")
    print("Default credentials: webadmin / WebAdmin0!")
    application.run(debug=True, port=5001)

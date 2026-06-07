"""
multitrack_wsgi.py — Platform dispatcher for PythonAnywhere.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON PYTHONANYWHERE — do NOT run this file with Python.
PA's WSGI server imports it automatically and calls `application`.
Point the PA WSGI config file field to this path and hit Reload.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOCAL TESTING ONLY — run the dispatcher on your own machine:
    export MULTITRACK_GPG_PASSPHRASE=test1234567890
    python multitrack_wsgi.py
    → http://127.0.0.1:8080/admin/login  (webadmin / WebAdmin0!)

Each Tracker block:
  1. Sets the Tracker's env vars (GPG passphrase + Flask secret key).
  2. Adds the Tracker's package root to sys.path (if outside this repo).
  3. Populates adminTracker.registry.TRACKERS before importing wsgi.py.
  4. Imports the Tracker's `application` callable from its wsgi.py.

The DispatcherMiddleware routes requests by URL prefix to the correct
Tracker. Unmatched prefixes return 404.
"""

import sys
import os
from pathlib import Path
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# ── pyMultiTaskWS root (makes `multitrack` and `adminTracker` importable) ─────
_pkg_root = str(Path(__file__).resolve().parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

# ── Tracker registry — shown on AdminTracker home page ────────────────────────
# Add one entry per mounted Tracker. `url` is the link the home page opens.
import adminTracker.registry as _reg
_reg.TRACKERS = [
    {
        "name":        "AdminTracker",
        "mount":       "/admin",
        "url":         "/admin/",
        "description": "Platform administration — user management & tracker index",
        "status":      "online",
    },
    # Uncomment when LLC Tracker is active:
    # {
    #     "name":        "LLC Accounting",
    #     "mount":       "/llc",
    #     "url":         "/llc/login",
    #     "description": "W&B Group LLC — double-entry ledger & IRS forms",
    #     "status":      "online",
    # },
]

# ── AdminTracker — platform administration Tracker ────────────────────────────
from adminTracker.wsgi import application as admin_app                  # noqa: E402

# ── LLC Tracker ───────────────────────────────────────────────────────────────
# Credentials set here — multitrack_wsgi.py is owner-readable only (mode 600).
# os.environ.setdefault("LLC_GPG_PASSPHRASE", "<llc-gpg-passphrase>")
# os.environ.setdefault("LLC_SECRET_KEY",     "<llc-secret-key>")
# sys.path.insert(0, "/home/wbgroup/llc/LLC-WB-Group/pages/AccountingData/Notebooks")
# from wsgi import application as llc_app                               # noqa: E402

# ── Future Tracker template (copy and fill in for each new Tracker) ───────────
# os.environ.setdefault("HEALTH_GPG_PASSPHRASE", "<health-gpg-passphrase>")
# sys.path.insert(0, "/home/wbgroup/trackHealth/<repo>/path/to/notebooks")
# from wsgi import application as health_app                            # noqa: E402

# ── Dispatcher ────────────────────────────────────────────────────────────────
# Each key is the URL mount point (must start with "/").
# The default app (NotFound) returns 404 for the bare domain root.
application = DispatcherMiddleware(NotFound(), {
    "/admin":       admin_app,
    # "/llc":         llc_app,
    # "/trackHealth": health_app,
})

if __name__ == "__main__":
    # LOCAL TESTING ONLY — PA never executes this block.
    from werkzeug.serving import run_simple
    print("MultiTrack dispatcher on http://127.0.0.1:8080")
    print("  /admin  → AdminTracker  (webadmin / WebAdmin0!)")
    run_simple("127.0.0.1", 8080, application, use_reloader=True, use_debugger=True)

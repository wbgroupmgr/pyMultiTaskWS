"""
multitrack_wsgi.py — Platform dispatcher for PythonAnywhere.

Copy this file to ~/multitrack_wsgi.py on PA and fill in the blanks.
The PA WSGI configuration file field should point here.

Each Tracker block:
  1. Sets the Tracker's env vars (GPG passphrase + Flask secret key).
  2. Adds the Tracker's Notebooks (or equivalent) dir to sys.path.
  3. Imports the Tracker's `application` callable from its wsgi.py.

The DispatcherMiddleware routes requests by URL prefix to the correct
Tracker. Unmatched prefixes return 404.
"""

import sys
import os
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# ── LLC Tracker ───────────────────────────────────────────────────────────────
# Credentials set here — multitrack_wsgi.py is owner-readable only (mode 600).
os.environ.setdefault("LLC_GPG_PASSPHRASE", "<llc-gpg-passphrase>")
os.environ.setdefault("LLC_SECRET_KEY",     "<llc-secret-key>")
sys.path.insert(0, "/home/wbgroup/llc/LLC-WB-Group/pages/AccountingData/Notebooks")
from wsgi import application as llc_app                                 # noqa: E402

# ── Future Tracker template (copy and fill in for each new Tracker) ───────────
# os.environ.setdefault("HEALTH_GPG_PASSPHRASE", "<health-gpg-passphrase>")
# os.environ.setdefault("HEALTH_SECRET_KEY",     "<health-secret-key>")
# sys.path.insert(0, "/home/wbgroup/trackHealth/<repo>/path/to/notebooks")
# from wsgi import application as health_app                            # noqa: E402

# ── Dispatcher ────────────────────────────────────────────────────────────────
# Each key is the URL mount point (must start with "/").
# The default app (NotFound) returns 404 for the bare domain root.
application = DispatcherMiddleware(NotFound(), {
    "/llc":         llc_app,
    # "/trackHealth": health_app,
})

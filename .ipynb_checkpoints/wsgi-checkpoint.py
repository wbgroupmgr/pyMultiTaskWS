"""
wsgi.py — PythonAnywhere WSGI entry point for MultiTaskWS.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON PYTHONANYWHERE — do NOT run this file with Python.
PA's WSGI server imports it automatically and calls `application`.
Point the PA WSGI config file field to this path and hit Reload.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For local testing use wsCmd.py instead:
    python3 wsCmd.py --start           # full dispatcher, Werkzeug dev server
    python3 wsCmd.py --start --wsgi    # same, no reloader (mirrors PA stack)
"""

import sys
from pathlib import Path

# pyMultiTaskWS/ root — makes multitrack.* and adminTracker.* importable.
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from wsCmd import WsCmd

application = WsCmd().make_application()

#!/usr/bin/env python3
"""
setupWebServerCmd.py — one-shot PythonAnywhere web server setup for pyMultiTaskWS.

Run from the pyMultiTaskWS/ directory after cloning the repo:
    python3.10 setupWebServerCmd.py

Tasks
─────
  1. Prompt for MULTITRACK_GPG_PASSPHRASE
  2. Install pip dependencies (flask, werkzeug)
  3. Seed trackerWeb/Accts/pw.json.gpg with default webadmin user
  4. Generate WEB_SECRET_KEY; store it in pw.json.gpg under _wsadmin
  5. Print the ready-to-paste ~/multitrack_wsgi.py content
"""

import getpass
import os
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Anchor pyMultiTaskWS/ on sys.path so multitrack.auth is importable.
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

from multitrack.auth import find_user, hash_password, load_users, save_users

# ── Config ────────────────────────────────────────────────────────────────────

DEPS = ["flask", "werkzeug"]

_DB_PATH = _here / "trackerWeb" / "Accts" / "pw.json.gpg"

_SEED_USER = {
    "username":   "webadmin",
    "password":   hash_password("WebAdmin0!"),
    "full_name":  "TrackerWeb Admin",
    "phone":      "",
    "role":       "member",
    "created_at": "2026-01-01T00:00:00",
}

_ADMIN_ID = "_wsadmin"


# ── Steps ─────────────────────────────────────────────────────────────────────

def step_passphrase() -> str:
    print("\n── Step 1: GPG Passphrase ──────────────────────────────────────")
    print("Encrypts the TrackerWeb user DB (trackerWeb/Accts/pw.json.gpg).")
    print("You must use the same passphrase every time the server runs.\n")
    while True:
        pp = getpass.getpass("  Enter MULTITRACK_GPG_PASSPHRASE (min 12 chars): ").strip()
        if len(pp) < 12:
            print("  ✗ Too short — at least 12 characters required.")
            continue
        if getpass.getpass("  Confirm passphrase: ").strip() != pp:
            print("  ✗ Passphrases do not match.")
            continue
        break
    os.environ["MULTITRACK_GPG_PASSPHRASE"] = pp
    print("  ✓ Passphrase accepted.")
    return pp


def step_pip() -> None:
    print("\n── Step 2: Install Dependencies ────────────────────────────────")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user", "--quiet"] + DEPS
    )
    if result.returncode != 0:
        print(f"  ✗ pip install failed. Run manually:")
        print(f"    pip install --user {' '.join(DEPS)}")
    else:
        print(f"  ✓ {', '.join(DEPS)} ready.")


def step_userdb() -> list:
    print("\n── Step 3: TrackerWeb User Database ────────────────────────────")
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    users = []

    if _DB_PATH.exists():
        try:
            users = load_users(_DB_PATH)
            print(f"  Found existing DB ({len(users)} user(s)).")
        except Exception as exc:
            print(f"  ✗ Could not read existing DB: {exc}")
            print("    Starting fresh.")
            users = []

    if not find_user(users, "webadmin"):
        users.append(_SEED_USER)
        print("  + Added seed user: webadmin / WebAdmin0!")
    else:
        print("  ✓ webadmin already present.")

    save_users(_DB_PATH, users)
    print(f"  ✓ Saved → {_DB_PATH}")
    return users


def step_secret_key(users: list) -> str:
    print("\n── Step 4: Web Server Secret Key ───────────────────────────────")
    secret_key = secrets.token_hex(32)
    os.environ["WEB_SECRET_KEY"] = secret_key

    admin = find_user(users, _ADMIN_ID)
    if admin:
        admin["notes"] = secret_key
        print(f"  Updated {_ADMIN_ID} with new secret key.")
    else:
        users.append({
            "username":   _ADMIN_ID,
            "password":   "",
            "full_name":  "webserver admin",
            "phone":      "",
            "role":       "admin",
            "notes":      secret_key,
            "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        })
        print(f"  + Created {_ADMIN_ID} record.")

    save_users(_DB_PATH, users)
    print(f"  ✓ WEB_SECRET_KEY stored in pw.json.gpg (notes field).")
    return secret_key


def step_wsgi(passphrase: str, secret_key: str) -> None:
    print("\n── Step 5: WSGI Configuration File ────────────────────────────")
    pa_username = Path.home().name
    pkg_path    = str(_here)

    wsgi_content = f"""\
import sys, os
from pathlib import Path
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# ── pyMultiTaskWS root (multitrack/ + trackerWeb/ importable from here) ───────
_pkg = {pkg_path!r}
if _pkg not in sys.path:
    sys.path.insert(0, _pkg)

# ── TrackerWeb — platform smoke-test ─────────────────────────────────────────
os.environ.setdefault('MULTITRACK_GPG_PASSPHRASE', {passphrase!r})
os.environ.setdefault('WEB_SECRET_KEY',            {secret_key!r})
from trackerWeb.wsgi import application as web_app

# ── LLC Tracker (uncomment after running LLC setup) ───────────────────────────
# os.environ.setdefault('LLC_GPG_PASSPHRASE', '<llc-passphrase>')
# os.environ.setdefault('LLC_SECRET_KEY',     '<llc-secret-key>')
# sys.path.insert(0, '/home/{pa_username}/llc/LLC-WB-Group/pages/AccountingData/Notebooks')
# from wsgi import application as llc_app

# ── Dispatcher ────────────────────────────────────────────────────────────────
application = DispatcherMiddleware(NotFound(), {{
    '/web': web_app,
    # '/llc': llc_app,
}})
"""

    print()
    print("  Copy the block below into ~/multitrack_wsgi.py")
    print("  Web tab → WSGI configuration file link → replace all content")
    print()
    print("  " + "─" * 62)
    for line in wsgi_content.splitlines():
        print("  " + line)
    print("  " + "─" * 62)
    print()
    print(f"  Detected PA username : {pa_username}")
    print(f"  pyMultiTaskWS path   : {pkg_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 64)
    print("  pyMultiTaskWS — PythonAnywhere Web Server Setup")
    print("=" * 64)

    passphrase = step_passphrase()
    step_pip()
    users      = step_userdb()
    secret_key = step_secret_key(users)
    step_wsgi(passphrase, secret_key)

    print("=" * 64)
    print("  Setup complete.")
    print("  → Paste the block above into ~/multitrack_wsgi.py")
    print("  → chmod 600 ~/multitrack_wsgi.py")
    print("  → Hit Reload in the PA Web tab.")
    print("  → Visit /web/login and sign in: webadmin / WebAdmin0!")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()

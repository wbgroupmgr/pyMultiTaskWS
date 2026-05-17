#!/usr/bin/env python3
"""
setupWebServerCmd.py — one-shot PythonAnywhere web server setup for pyMultiTaskWS.

Run from the pyMultiTaskWS/ directory after cloning the repo:
    python3.10 setupWebServerCmd.py

Tasks
─────
  1. Prompt for MULTITRACK_GPG_PASSPHRASE
  2. Install pip dependencies (flask, werkzeug)
  3. Seed adminTracker/Accts/pw.json.gpg with default webadmin user
  4. Generate WEB_SECRET_KEY; store in adminProfile.json + pw.json.gpg
  5. Print the ready-to-paste ~/multitrack_wsgi.py content
"""

import getpass
import json
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

_DB_PATH  = _here / "adminTracker" / "Accts" / "pw.json.gpg"
_PROFILE  = _here / "adminTracker" / "Accts" / "adminProfile.json"
_ADMIN_ID = "wbgadminWS"

_SEED_USER = {
    "username":   "webadmin",
    "password":   hash_password("WebAdmin0!"),
    "full_name":  "WBGroup Admin",
    "phone":      "",
    "role":       "member",
    "created_at": "2026-01-01T00:00:00",
}


# ── Steps ─────────────────────────────────────────────────────────────────────

def step_passphrase() -> str:
    print("\n── Step 1: GPG Passphrase ──────────────────────────────────────")
    print("Encrypts the AdminTracker user DB (adminTracker/Accts/pw.json.gpg).")
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
    print("\n── Step 3: AdminTracker User Database ──────────────────────────")
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


def step_secret_key(passphrase: str, users: list) -> str:
    print("\n── Step 4: Web Server Secret Key ───────────────────────────────")
    secret_key = secrets.token_hex(32)
    os.environ["WEB_SECRET_KEY"] = secret_key

    # Store in adminProfile.json for easy credential recovery.
    profile = {}
    if _PROFILE.exists():
        try:
            profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    profile["MultiTaskWS_Config"] = {
        "WEB_SECRET_KEY":            secret_key,
        "MULTITRACK_GPG_PASSPHRASE": passphrase,
        "WebServer":                 f"Host_{Path.home().name}",
    }
    _PROFILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Saved MultiTaskWS_Config → {_PROFILE.name}")

    # Also store a marker record in pw.json.gpg.
    admin = find_user(users, _ADMIN_ID)
    if admin:
        admin["notes"] = f"Config in {_PROFILE.name} → MultiTaskWS_Config."
        print(f"  Updated {_ADMIN_ID} notes.")
    else:
        users.append({
            "username":   _ADMIN_ID,
            "password":   "",
            "full_name":  "webserver admin",
            "phone":      "",
            "role":       "member",
            "notes":      f"Config in {_PROFILE.name} → MultiTaskWS_Config.",
            "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        })
        print(f"  + Created {_ADMIN_ID} record.")

    save_users(_DB_PATH, users)
    print(f"  ✓ WEB_SECRET_KEY stored in adminProfile.json and pw.json.gpg.")
    return secret_key


def step_wsgi(passphrase: str, secret_key: str) -> None:
    print("\n── Step 5: WSGI Configuration File ────────────────────────────")
    pkg_path = str(_here)

    wsgi_content = f"""\
import sys, os
from pathlib import Path
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# ── pyMultiTaskWS root ────────────────────────────────────────────────────────
_pkg = {pkg_path!r}
if _pkg not in sys.path:
    sys.path.insert(0, _pkg)

# ── Tracker registry (shown on AdminTracker home page) ────────────────────────
import adminTracker.registry as _reg
_reg.TRACKERS = [
    {{
        "name":        "AdminTracker",
        "mount":       "/admin",
        "url":         "/admin/",
        "description": "Platform administration — user management & tracker index",
        "status":      "online",
    }},
    # Add more Trackers here as they go live.
]

# ── AdminTracker ──────────────────────────────────────────────────────────────
os.environ.setdefault('MULTITRACK_GPG_PASSPHRASE', {passphrase!r})
os.environ.setdefault('WEB_SECRET_KEY',            {secret_key!r})
from adminTracker.wsgi import application as admin_app

# ── LLC Tracker (uncomment after running LLC setup) ───────────────────────────
# os.environ.setdefault('LLC_GPG_PASSPHRASE', '<llc-passphrase>')
# os.environ.setdefault('LLC_SECRET_KEY',     '<llc-secret-key>')
# sys.path.insert(0, '/home/wbgroup/llc/LLC-WB-Group/pages/AccountingData/Notebooks')
# from wsgi import application as llc_app

# ── Dispatcher ────────────────────────────────────────────────────────────────
application = DispatcherMiddleware(NotFound(), {{
    '/admin': admin_app,
    # '/llc':   llc_app,
}})
"""

    print()
    print("  Copy the block below into ~/multitrack_wsgi.py on PythonAnywhere.")
    print("  Web tab → WSGI configuration file link → replace all content.")
    print()
    print("  " + "─" * 62)
    for line in wsgi_content.splitlines():
        print("  " + line)
    print("  " + "─" * 62)
    print()
    print(f"  pyMultiTaskWS path : {pkg_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 64)
    print("  pyMultiTaskWS — PythonAnywhere Web Server Setup")
    print("=" * 64)

    passphrase = step_passphrase()
    step_pip()
    users      = step_userdb()
    secret_key = step_secret_key(passphrase, users)
    step_wsgi(passphrase, secret_key)

    print("=" * 64)
    print("  Setup complete.")
    print("  → Paste the block above into ~/multitrack_wsgi.py")
    print("  → chmod 600 ~/multitrack_wsgi.py")
    print("  → Hit Reload in the PA Web tab.")
    print("  → Visit /admin/login and sign in: webadmin / WebAdmin0!")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()

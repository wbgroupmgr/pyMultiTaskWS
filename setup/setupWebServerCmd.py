#!/usr/bin/env python3
"""
setupWebServerCmd.py — interactive PythonAnywhere setup for a MultiTrack Tracker.

Run once per Tracker, from the Tracker's Notebooks (sys.path root) directory:
    python3.10 /path/to/pyMultiTaskWS/setup/setupWebServerCmd.py \
        --tracker-name "My Tracker" \
        --tracker-id   mytracker \
        --db           /home/<user>/<trackerid>/<repo>/Accts/pw.json.gpg \
        --notebooks    /home/<user>/<trackerid>/<repo>/path/to/notebooks \
        --seed-user    admin \
        --seed-pass    "Admin0Pass!" \
        --seed-role    member

Tasks
─────
  1. Prompt for MULTITRACK_GPG_PASSPHRASE (min 12 chars)
  2. Install pip dependencies (flask werkzeug)
  3. Seed the Tracker's pw.json.gpg with the seed user (if absent)
  4. Generate a Flask SECRET_KEY; store it in pw.json.gpg under _wsadmin
  5. Print the Tracker block to add to ~/multitrack_wsgi.py
"""

import argparse
import getpass
import os
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_here = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_here))

from multitrack.auth import find_user, hash_password, load_users, save_users

DEPS = ["flask", "werkzeug"]
_ADMIN_ID = "_wsadmin"
_ENV_PP   = "MULTITRACK_GPG_PASSPHRASE"


def step_passphrase(tracker_id: str) -> str:
    env_var = f"{tracker_id.upper()}_GPG_PASSPHRASE"
    print(f"\n── Step 1: GPG Passphrase ──────────────────────────────────────")
    print(f"Encrypts the user DB (pw.json.gpg).")
    print(f"Env var: {env_var}  (set in multitrack_wsgi.py)\n")
    while True:
        pp = getpass.getpass("  Enter passphrase (min 12 chars): ").strip()
        if len(pp) < 12:
            print("  ✗ Too short — at least 12 characters required.")
            continue
        if getpass.getpass("  Confirm passphrase: ").strip() != pp:
            print("  ✗ Passphrases do not match.")
            continue
        break
    os.environ[_ENV_PP] = pp
    print("  ✓ Passphrase accepted.")
    return pp


def step_pip(extra_deps: list) -> None:
    print("\n── Step 2: Install Dependencies ────────────────────────────────")
    all_deps = DEPS + extra_deps
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user", "--quiet"] + all_deps
    )
    if result.returncode != 0:
        print(f"  ✗ pip install failed. Run manually:")
        print(f"    pip install --user {' '.join(all_deps)}")
    else:
        print(f"  ✓ {', '.join(all_deps)} ready.")


def step_userdb(db_path: Path, seed_user: str, seed_pass: str, seed_role: str) -> list:
    print("\n── Step 3: User Database ───────────────────────────────────────")
    users = []
    if db_path.exists():
        try:
            users = load_users(db_path)
            print(f"  Found existing DB ({len(users)} user(s)).")
        except Exception as exc:
            print(f"  ✗ Could not read existing DB: {exc}")
            print("    Starting fresh.")
            users = []

    if not find_user(users, seed_user):
        users.append({
            "username":   seed_user,
            "password":   hash_password(seed_pass),
            "full_name":  seed_user,
            "phone":      "",
            "role":       seed_role,
            "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        })
        print(f"  + Added seed user: {seed_user} / {seed_pass}")
    else:
        print(f"  ✓ Seed user '{seed_user}' already present.")

    save_users(db_path, users)
    print(f"  ✓ Saved → {db_path}")
    return users


def step_secret_key(db_path: Path, users: list) -> str:
    print("\n── Step 4: Flask Secret Key ────────────────────────────────────")
    secret_key = secrets.token_hex(32)

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

    save_users(db_path, users)
    print(f"  ✓ SECRET_KEY stored in pw.json.gpg (notes field).")
    return secret_key


def step_wsgi_block(tracker_id: str, passphrase: str, secret_key: str,
                    notebooks_path: str) -> None:
    print("\n── Step 5: multitrack_wsgi.py Tracker Block ────────────────────")
    tid = tracker_id.upper()
    block = f"""\
# ── {tracker_id} Tracker ──
os.environ.setdefault('{tid}_GPG_PASSPHRASE', {passphrase!r})
os.environ.setdefault('{tid}_SECRET_KEY',     {secret_key!r})
sys.path.insert(0, {notebooks_path!r})
from wsgi import application as {tracker_id}_app
"""
    mount_line = f'    "/{tracker_id}": {tracker_id}_app,'

    print()
    print("  Add this block BEFORE the DispatcherMiddleware call in ~/multitrack_wsgi.py:")
    print("  " + "─" * 62)
    for line in block.splitlines():
        print("  " + line)
    print("  " + "─" * 62)
    print()
    print("  Then add this line inside DispatcherMiddleware({...}):")
    print(f"    {mount_line}")


def main():
    ap = argparse.ArgumentParser(description="MultiTrack Tracker setup")
    ap.add_argument("--tracker-name", required=True, help="Display name, e.g. 'LLC Editor'")
    ap.add_argument("--tracker-id",   required=True, help="URL slug, e.g. 'llc'")
    ap.add_argument("--db",           required=True, help="Path to pw.json.gpg")
    ap.add_argument("--notebooks",    required=True, help="sys.path root (Notebooks dir)")
    ap.add_argument("--seed-user",    default="admin")
    ap.add_argument("--seed-pass",    default="Admin0Pass!")
    ap.add_argument("--seed-role",    default="member")
    ap.add_argument("--extra-deps",   nargs="*", default=[],
                    help="Additional pip packages to install")
    args = ap.parse_args()

    db_path = Path(args.db)

    print()
    print("=" * 64)
    print(f"  MultiTrack — {args.tracker_name} Tracker Setup")
    print("=" * 64)

    passphrase = step_passphrase(args.tracker_id)
    step_pip(args.extra_deps)
    users      = step_userdb(db_path, args.seed_user, args.seed_pass, args.seed_role)
    secret_key = step_secret_key(db_path, users)
    step_wsgi_block(args.tracker_id, passphrase, secret_key, args.notebooks)

    print("=" * 64)
    print("  Setup complete.")
    print(f"  → Update ~/multitrack_wsgi.py with the block above.")
    print(f"  → Hit Reload in the PA Web tab.")
    print(f"  → Visit /<tracker-id>/login and sign in: {args.seed_user} / {args.seed_pass}")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()

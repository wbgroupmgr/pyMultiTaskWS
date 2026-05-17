#!/usr/bin/env python3
"""
adminTracker/wsCmd.py — AdminTracker web server management.

Run from the pyMultiTaskWS/ directory.

Setup (first time or reset forgotten passphrase):
    python3 adminTracker/wsCmd.py --setup
    python3 adminTracker/wsCmd.py --setup --reset

Start locally (standalone, no dispatcher):
    MULTITRACK_GPG_PASSPHRASE=<pp> python3 adminTracker/wsCmd.py --start
    MULTITRACK_GPG_PASSPHRASE=<pp> python3 adminTracker/wsCmd.py --start --port 8081

Start via dispatcher (PythonAnywhere):
    python3 multitrack_wsgi.py   (or PA Reload — runs as WSGI)
"""

import argparse
import getpass
import json
import os
import platform
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Anchor pyMultiTaskWS/ on sys.path so multitrack.auth is importable.
_pkg_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_pkg_root))

from multitrack.auth import find_user, hash_password, load_users, save_users

# ── Constants ─────────────────────────────────────────────────────────────────

DEPS = ["flask", "werkzeug"]

_HERE    = Path(__file__).resolve().parent
_DB_PATH = _HERE / "Accts" / "pw.json.gpg"
_PROFILE = _HERE / "Accts" / "adminProfile.json"

_ADMIN_ID = "wbgadminWS"

_SEED_USER = {
    "username":   "webadmin",
    "password":   hash_password("WebAdmin0!"),
    "full_name":  "WBGroup Admin",
    "phone":      "",
    "role":       "member",
    "created_at": "2026-01-01T00:00:00",
}


# ── WsCmd class ───────────────────────────────────────────────────────────────

class WsCmd:
    def __init__(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _webserver_tag(self) -> str:
        home = Path.home()
        if str(home).startswith("/home/"):        # PythonAnywhere Linux
            return f"Host_{home.name}"
        return f"local_{platform.node()}"

    def _load_profile(self) -> dict:
        if _PROFILE.exists():
            return json.loads(_PROFILE.read_text(encoding="utf-8"))
        return {}

    def _save_profile(self, profile: dict) -> None:
        _PROFILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    def _inject_env_from_profile(self) -> None:
        """Set MULTITRACK_GPG_PASSPHRASE and WEB_SECRET_KEY from profile if not in env."""
        cfg = self._load_profile()
        for env_var in ("MULTITRACK_GPG_PASSPHRASE", "WEB_SECRET_KEY"):
            if not os.environ.get(env_var) and cfg.get(env_var):
                os.environ[env_var] = cfg[env_var]

    # ── setup steps ───────────────────────────────────────────────────────────

    def _reset_db(self) -> None:
        print("\n── Step 0: Reset User Database ─────────────────────────────────")
        if not _DB_PATH.exists():
            print("  No existing DB found — nothing to delete.")
            return
        print(f"  ⚠️  This will permanently delete: {_DB_PATH}")
        print("  All existing user accounts will be lost.")
        if input("  Type YES to confirm: ").strip() != "YES":
            print("  Cancelled — database not deleted.")
            sys.exit(0)
        _DB_PATH.unlink()
        print("  ✓ Deleted pw.json.gpg — starting fresh.")

    def _prompt_passphrase(self) -> str:
        print("\n── Step 1: GPG Passphrase ──────────────────────────────────────")
        print("Encrypts the AdminTracker user DB (Accts/pw.json.gpg).")
        print("Use the same passphrase every time the server runs.\n")
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

    def _install_deps(self) -> None:
        print("\n── Step 2: Install Dependencies ────────────────────────────────")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "--quiet"] + DEPS
        )
        if result.returncode != 0:
            print(f"  ✗ pip install failed. Run manually:")
            print(f"    pip install --user {' '.join(DEPS)}")
        else:
            print(f"  ✓ {', '.join(DEPS)} ready.")

    def _write_profile_config(self, passphrase: str) -> str:
        print("\n── Step 3: AdminTracker Config → adminProfile.json ─────────────")
        secret_key = secrets.token_hex(32)
        os.environ["WEB_SECRET_KEY"] = secret_key
        tag = self._webserver_tag()

        profile = self._load_profile()
        profile["MultiTaskWS_Config"] = {
            "WEB_SECRET_KEY":           secret_key,
            "MULTITRACK_GPG_PASSPHRASE": passphrase,
            "WebServer":                tag,
        }
        self._save_profile(profile)

        print(f"  ✓ Saved MultiTaskWS_Config → {_PROFILE.name}")
        print(f"    WEB_SECRET_KEY           : {secret_key[:16]}…")
        print(f"    MULTITRACK_GPG_PASSPHRASE: {'*' * len(passphrase)}")
        print(f"    WebServer                : {tag}")
        return secret_key

    def _seed_userdb(self) -> None:
        print("\n── Step 4: User Database ───────────────────────────────────────")
        users = []

        if _DB_PATH.exists():
            try:
                users = load_users(_DB_PATH)
                print(f"  Found existing DB ({len(users)} user(s)).")
            except Exception as exc:
                print(f"  ✗ Could not read existing DB: {exc}")
                print("    Starting fresh.")

        if not find_user(users, "webadmin"):
            users.append(_SEED_USER)
            print("  + Added seed user: webadmin / WebAdmin0!")
        else:
            print("  ✓ webadmin already present.")

        admin = find_user(users, _ADMIN_ID)
        if admin:
            admin["notes"] = "Config in adminTracker/Accts/adminProfile.json → MultiTaskWS_Config."
            print(f"  Updated {_ADMIN_ID} notes.")
        else:
            users.append({
                "username":   _ADMIN_ID,
                "password":   "",
                "full_name":  "webserver admin",
                "phone":      "",
                "role":       "member",
                "notes":      "Config in adminTracker/Accts/adminProfile.json → MultiTaskWS_Config.",
                "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            })
            print(f"  + Created {_ADMIN_ID} record.")

        save_users(_DB_PATH, users)
        print(f"  ✓ Saved → {_DB_PATH}")

    # ── public commands ───────────────────────────────────────────────────────

    def setup(self, reset: bool = False) -> None:
        """Set up AdminTracker (passphrase, deps, profile config, user DB)."""
        print()
        print("=" * 64)
        print("  AdminTracker — Setup")
        print("=" * 64)

        if reset:
            self._reset_db()

        passphrase = self._prompt_passphrase()
        self._install_deps()
        self._write_profile_config(passphrase)
        self._seed_userdb()

        print()
        print("=" * 64)
        print("  Setup complete.")
        print(f"  Credentials stored in: {_PROFILE}")
        print()
        print("  Recover credentials any time:")
        print(f"    python3 -c \"import json; print(json.dumps(")
        print(f"      json.load(open('{_PROFILE}'))['MultiTaskWS_Config'],")
        print( "      indent=2))\"")
        print()
        print("  Start locally:")
        print("    MULTITRACK_GPG_PASSPHRASE=<pp> python3 adminTracker/wsCmd.py --start")
        print()
        print("  Start via dispatcher (PythonAnywhere):")
        print("    → Hit Reload in the PA Web tab")
        print("    → Visit /admin/login   (webadmin / WebAdmin0!)")
        print("=" * 64)
        print()

    def start(self, addr: str = "127.0.0.1", port: int = 8081, debug: bool = False) -> None:
        """Start AdminTracker locally (standalone, not via dispatcher)."""
        self._inject_env_from_profile()

        from adminTracker.app import AdminTrackerApp

        print()
        print("=" * 64)
        print(f"  AdminTracker — Local Start")
        print(f"  http://{addr}:{port}/login")
        print("=" * 64)

        app_obj = AdminTrackerApp(db_path=_DB_PATH, trackers=[], tracker_name="AdminTracker")
        app_obj.app.run(host=addr, port=port, debug=debug)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wsCmd",
        description="AdminTracker web server management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 adminTracker/wsCmd.py --setup
  python3 adminTracker/wsCmd.py --setup --reset
  MULTITRACK_GPG_PASSPHRASE=<pp> python3 adminTracker/wsCmd.py --start
  MULTITRACK_GPG_PASSPHRASE=<pp> python3 adminTracker/wsCmd.py --start --port 8081
""",
    )

    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--setup", action="store_true",
                      help="Set up AdminTracker (passphrase, deps, user DB)")
    mode.add_argument("--start", action="store_true",
                      help="Start AdminTracker locally")

    ap.add_argument("--reset", action="store_true",
                    help="[--setup] Delete pw.json.gpg before setup")
    ap.add_argument("--addr", default="127.0.0.1", metavar="IP",
                    help="[--start] Flask bind address (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8081,
                    help="[--start] Flask port (default: 8081)")
    ap.add_argument("--debug", action="store_true",
                    help="[--start] Enable Flask debug mode")

    return ap


def main():
    args = _build_parser().parse_args()
    ws   = WsCmd()

    if args.setup:
        ws.setup(reset=args.reset)
    else:
        ws.start(addr=args.addr, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

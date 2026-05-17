#!/usr/bin/env python3
"""
adminTracker/wsCmd.py — AdminTracker management (tracker-level).

Run from the pyMultiTaskWS/ directory.

Preferred workflow: run platform setup first, then use this for DB reseeds or local dev.
    python3 wsCmd.py --setup                      # platform setup (sets passphrase, config)
    python3 adminTracker/wsCmd.py --setup         # reseed adminTracker user DB only
    python3 adminTracker/wsCmd.py --setup --reset # delete DB then reseed

Start AdminTracker standalone (no dispatcher URL prefix, port 8081):
    python3 adminTracker/wsCmd.py --start
    python3 adminTracker/wsCmd.py --start --port 8081 --debug

For the full dispatcher (all Trackers with URL prefixes) use the platform wsCmd:
    python3 wsCmd.py --start
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# pyMultiTaskWS/ root
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from multitrack.auth import find_user, hash_password, load_users, save_users

# ── Constants ─────────────────────────────────────────────────────────────────

_HERE    = Path(__file__).resolve().parent
_DB_PATH = _HERE / "Accts" / "pw.json.gpg"

_PLATFORM_CONFIG = Path.home() / ".MultiTaskWS" / "MultiTaskWS_config.json"

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
    """
    AdminTracker tracker-level manager.

    Reads MULTITRACK_GPG_PASSPHRASE and WEB_SECRET_KEY from env or
    ~/.MultiTaskWS/MultiTaskWS_config.json (written by platform wsCmd.py --setup).
    """

    def __init__(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _inject_env_from_platform(self) -> None:
        """Pull credentials from platform config if not already in env."""
        if not _PLATFORM_CONFIG.exists():
            return
        try:
            cfg = json.loads(_PLATFORM_CONFIG.read_text(encoding="utf-8"))
            for var in ("MULTITRACK_GPG_PASSPHRASE", "WEB_SECRET_KEY"):
                if not os.environ.get(var) and cfg.get(var):
                    os.environ[var] = cfg[var]
        except Exception:
            pass

    # ── setup steps ───────────────────────────────────────────────────────────

    def _reset_db(self) -> None:
        if not _DB_PATH.exists():
            print("  No existing DB found — nothing to delete.")
            return
        print(f"  ⚠️  This will permanently delete: {_DB_PATH}")
        if input("  Type YES to confirm: ").strip() != "YES":
            print("  Cancelled.")
            sys.exit(0)
        _DB_PATH.unlink()
        print("  ✓ Deleted pw.json.gpg — starting fresh.")

    def _seed_userdb(self) -> None:
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
            admin["notes"] = f"Config in {_PLATFORM_CONFIG}"
            print(f"  Updated {_ADMIN_ID} notes.")
        else:
            users.append({
                "username":   _ADMIN_ID,
                "password":   "",
                "full_name":  "webserver admin",
                "phone":      "",
                "role":       "member",
                "notes":      f"Config in {_PLATFORM_CONFIG}",
                "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            })
            print(f"  + Created {_ADMIN_ID} record.")

        save_users(_DB_PATH, users)
        print(f"  ✓ Saved → {_DB_PATH}")

    # ── public commands ───────────────────────────────────────────────────────

    def setup(self, reset: bool = False) -> None:
        """Seed the AdminTracker user DB. Reads credentials from platform config."""
        print()
        print("=" * 64)
        print("  AdminTracker — Setup")
        print("=" * 64)

        self._inject_env_from_platform()

        if not os.environ.get("MULTITRACK_GPG_PASSPHRASE"):
            print("  ✗ MULTITRACK_GPG_PASSPHRASE not set and platform config not found.")
            print(f"    Run: python3 wsCmd.py --setup  (from pyMultiTaskWS/)")
            print(f"    or:  export MULTITRACK_GPG_PASSPHRASE=<passphrase>")
            sys.exit(1)

        if reset:
            self._reset_db()

        self._seed_userdb()

        print()
        print("=" * 64)
        print("  Setup complete.")
        print(f"  User DB: {_DB_PATH}")
        print("=" * 64)
        print()

    def start(self, addr: str = "127.0.0.1", port: int = 8081, debug: bool = False) -> None:
        """Start AdminTracker standalone (no dispatcher prefix, mount at /)."""
        self._inject_env_from_platform()

        if not os.environ.get("MULTITRACK_GPG_PASSPHRASE"):
            print("  ✗ MULTITRACK_GPG_PASSPHRASE not set.")
            print(f"    Run: python3 wsCmd.py --setup  (from pyMultiTaskWS/)")
            sys.exit(1)

        from adminTracker.app import AdminTrackerApp

        print()
        print("=" * 64)
        print(f"  AdminTracker — Standalone Start  (http://{addr}:{port}/login)")
        print("  Note: no URL prefix — running outside dispatcher.")
        print("=" * 64)

        app_obj = AdminTrackerApp(db_path=_DB_PATH, trackers=[], tracker_name="AdminTracker")
        app_obj.app.run(host=addr, port=port, debug=debug)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="adminTracker/wsCmd",
        description="AdminTracker tracker-level management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 adminTracker/wsCmd.py --setup
  python3 adminTracker/wsCmd.py --setup --reset
  python3 adminTracker/wsCmd.py --start
  python3 adminTracker/wsCmd.py --start --port 8081 --debug
""",
    )

    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--setup", action="store_true",
                      help="Seed AdminTracker user DB (reads passphrase from platform config)")
    mode.add_argument("--start", action="store_true",
                      help="Start AdminTracker standalone (port 8081, no dispatcher)")

    ap.add_argument("--reset", action="store_true",
                    help="[--setup] Delete pw.json.gpg before seeding")
    ap.add_argument("--addr", default="127.0.0.1", metavar="IP",
                    help="[--start] Bind address (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8081,
                    help="[--start] Port (default: 8081)")
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

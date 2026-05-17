#!/usr/bin/env python3
"""
wsCmd.py — MultiTaskWS platform management.

Run from the pyMultiTaskWS/ directory.

Setup (first time or reset):
    python3 wsCmd.py --setup
    python3 wsCmd.py --setup --reset

Start locally (full WSGI dispatcher with all mounted Trackers):
    python3 wsCmd.py --start
    python3 wsCmd.py --start --local --port 8080

Start in WSGI mode (full dispatcher, mirrors PA environment):
    python3 wsCmd.py --start --wsgi

PythonAnywhere: wsgi.py imports make_application() — no CLI args needed.

Config stored in: ~/.MultiTaskWS/MultiTaskWS_config.json
"""

import argparse
import getpass
import importlib.util
import json
import os
import platform
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Anchor pyMultiTaskWS/ on sys.path so multitrack.* and adminTracker.* are importable.
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from multitrack.auth import find_user, hash_password, load_users, save_users

# ── Constants ─────────────────────────────────────────────────────────────────

DEPS = ["flask", "werkzeug"]

_ADMIN_DB  = _here / "adminTracker" / "Accts" / "pw.json.gpg"
_ADMIN_ID  = "wbgadminWS"

_SEED_USER = {
    "username":   "webadmin",
    "password":   hash_password("WebAdmin0!"),
    "full_name":  "WBGroup Admin",
    "phone":      "",
    "role":       "member",
    "created_at": "2026-01-01T00:00:00",
}

_DEFAULT_TRACKERS = [
    {
        "name":        "AdminTracker",
        "mount":       "/admin",
        "url":         "/admin/",
        "description": "Platform administration — user management & tracker index",
        "status":      "online",
        "builtin":     True,
    }
]


# ── WsCmd class ───────────────────────────────────────────────────────────────

class WsCmd:
    """
    MultiTaskWS platform manager.

    Config: ~/.MultiTaskWS/MultiTaskWS_config.json
      MULTITRACK_GPG_PASSPHRASE  — GPG passphrase for all Tracker user DBs
      WEB_SECRET_KEY             — Flask session signing key
      WebServer                  — 'Host_<pa-user>' or 'local_<machine>'
      Trackers                   — list of Tracker entries (see _DEFAULT_TRACKERS)
        Each entry: name, mount, url, description, status, builtin (bool)
        External trackers also: sys_path, env {KEY: VALUE, ...}
    """

    CONFIG_DIR  = Path.home() / ".MultiTaskWS"
    CONFIG_PATH = CONFIG_DIR  / "MultiTaskWS_config.json"

    def __init__(self):
        pass

    # ── helpers ───────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        if not self.CONFIG_PATH.exists():
            return {}
        return json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))

    def _save_config(self, cfg: dict) -> None:
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.CONFIG_PATH.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.CONFIG_PATH.chmod(0o600)

    def _inject_env(self) -> None:
        """Set MULTITRACK_GPG_PASSPHRASE and WEB_SECRET_KEY from config if not in env."""
        cfg = self._load_config()
        for var in ("MULTITRACK_GPG_PASSPHRASE", "WEB_SECRET_KEY"):
            if not os.environ.get(var) and cfg.get(var):
                os.environ[var] = cfg[var]

    def _webserver_tag(self) -> str:
        home = Path.home()
        if str(home).startswith("/home/"):
            return f"Host_{home.name}"
        return f"local_{platform.node()}"

    # ── setup steps ───────────────────────────────────────────────────────────

    def _reset_config(self) -> None:
        print("\n── Step 0: Reset Configuration ─────────────────────────────────")
        targets = []
        if self.CONFIG_PATH.exists():
            targets.append(self.CONFIG_PATH)
        if _ADMIN_DB.exists():
            targets.append(_ADMIN_DB)
        if not targets:
            print("  Nothing to reset.")
            return
        for t in targets:
            print(f"  ⚠️  Will delete: {t}")
        if input("  Type YES to confirm: ").strip() != "YES":
            print("  Cancelled.")
            sys.exit(0)
        for t in targets:
            t.unlink()
            print(f"  ✓ Deleted {t.name}")

    def _prompt_passphrase(self) -> str:
        print("\n── Step 1: GPG Passphrase ──────────────────────────────────────")
        print("Used to encrypt every Tracker user DB (pw.json.gpg).")
        print("Must be the same passphrase each time the server runs.\n")
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

    def _seed_admin_db(self) -> None:
        print("\n── Step 3: AdminTracker User Database ──────────────────────────")
        _ADMIN_DB.parent.mkdir(parents=True, exist_ok=True)
        users = []
        if _ADMIN_DB.exists():
            try:
                users = load_users(_ADMIN_DB)
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
            admin["notes"] = f"Config in {self.CONFIG_PATH}"
            print(f"  Updated {_ADMIN_ID} notes.")
        else:
            users.append({
                "username":   _ADMIN_ID,
                "password":   "",
                "full_name":  "webserver admin",
                "phone":      "",
                "role":       "member",
                "notes":      f"Config in {self.CONFIG_PATH}",
                "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            })
            print(f"  + Created {_ADMIN_ID} record.")

        save_users(_ADMIN_DB, users)
        print(f"  ✓ Saved → {_ADMIN_DB}")

    def _write_config(self, passphrase: str, secret_key: str) -> None:
        print("\n── Step 4: Write Platform Config ───────────────────────────────")
        cfg = self._load_config()
        cfg["MULTITRACK_GPG_PASSPHRASE"] = passphrase
        cfg["WEB_SECRET_KEY"]            = secret_key
        cfg["WebServer"]                 = self._webserver_tag()
        cfg.setdefault("Trackers", _DEFAULT_TRACKERS)
        self._save_config(cfg)
        print(f"  ✓ Saved → {self.CONFIG_PATH}")
        print(f"    MULTITRACK_GPG_PASSPHRASE : {'*' * len(passphrase)}")
        print(f"    WEB_SECRET_KEY            : {secret_key[:16]}…")
        print(f"    WebServer                 : {cfg['WebServer']}")

    # ── application builder (used by wsgi.py and --start --wsgi) ─────────────

    def make_application(self):
        """
        Build and return the WSGI DispatcherMiddleware application.

        Called by wsgi.py (PA entry point) and by --start --wsgi locally.
        Loads config, sets env vars, populates tracker registry, imports
        each Tracker's wsgi.py, and returns the fully wired application.
        """
        self._inject_env()
        cfg      = self._load_config()
        trackers = cfg.get("Trackers", _DEFAULT_TRACKERS)

        # Strip internal-only keys before injecting into registry.
        import adminTracker.registry as _reg
        _reg.TRACKERS = [
            {k: v for k, v in t.items() if k not in ("builtin", "sys_path", "env")}
            for t in trackers
        ]

        # AdminTracker is always built-in.
        from adminTracker.wsgi import application as admin_app
        mounts = {"/admin": admin_app}

        # External Trackers — each entry needs sys_path and optionally env.
        for t in trackers:
            if t.get("builtin"):
                continue
            sys_path = t.get("sys_path", "")
            if sys_path and sys_path not in sys.path:
                sys.path.insert(0, sys_path)
            for env_key, env_val in t.get("env", {}).items():
                os.environ.setdefault(env_key, env_val)
            wsgi_file = Path(sys_path) / "wsgi.py" if sys_path else None
            if not wsgi_file or not wsgi_file.exists():
                print(f"  ✗ {t['name']}: wsgi.py not found at {wsgi_file}")
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"tracker_{t['mount'].strip('/')}_wsgi", str(wsgi_file)
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mounts[t["mount"]] = mod.application
                print(f"  ✓ Mounted {t['name']} at {t['mount']}")
            except Exception as exc:
                print(f"  ✗ {t['name']}: failed to import wsgi.py — {exc}")

        from werkzeug.middleware.dispatcher import DispatcherMiddleware
        from werkzeug.exceptions import NotFound
        return DispatcherMiddleware(NotFound(), mounts)

    # ── public commands ───────────────────────────────────────────────────────

    def setup(self, reset: bool = False) -> None:
        """Interactive platform setup — writes ~/.MultiTaskWS/MultiTaskWS_config.json."""
        print()
        print("=" * 64)
        print("  MultiTaskWS — Platform Setup")
        print("=" * 64)

        if reset:
            self._reset_config()

        passphrase = self._prompt_passphrase()
        self._install_deps()
        self._seed_admin_db()
        secret_key = secrets.token_hex(32)
        os.environ["WEB_SECRET_KEY"] = secret_key
        self._write_config(passphrase, secret_key)

        print()
        print("=" * 64)
        print("  Setup complete.")
        print(f"  Config : {self.CONFIG_PATH}")
        print()
        print("  Recover credentials any time:")
        print(f"    python3 -c \"import json; cfg=json.load(open('{self.CONFIG_PATH}')); print(cfg['MULTITRACK_GPG_PASSPHRASE'])\"")
        print()
        print("  Start locally (full WSGI dispatcher):")
        print("    python3 wsCmd.py --start")
        print()
        print("  On PythonAnywhere:")
        print("    → Point WSGI config file to: wsgi.py")
        print("    → Hit Reload in the Web tab")
        print("    → Visit /admin/login  (webadmin / WebAdmin0!)")
        print("=" * 64)
        print()

    def start(self, wsgi_mode: bool = False,
              addr: str = "127.0.0.1", port: int = None,
              debug: bool = False) -> None:
        """
        Start the MultiTaskWS dispatcher.

        --start (default / --local):
            Full WSGI dispatcher via Werkzeug dev server on port 8080.
            Same behavior as the old `python multitrack_wsgi.py`.

        --start --wsgi:
            Same full dispatcher, but runs with reloader off (closer to PA behavior).
            Useful for smoke-testing the production-like WSGI stack locally.
        """
        _port = port or 8080

        print()
        print("=" * 64)
        if wsgi_mode:
            print(f"  MultiTaskWS — WSGI Start  (http://{addr}:{_port})")
        else:
            print(f"  MultiTaskWS — Local Start  (http://{addr}:{_port})")
        print("=" * 64)

        application = self.make_application()

        cfg      = self._load_config()
        trackers = cfg.get("Trackers", _DEFAULT_TRACKERS)
        for t in trackers:
            print(f"  {t['mount']:10s} → {t['name']}")

        print()
        if wsgi_mode:
            print("  [WSGI mode] Running without reloader or debugger.")
        else:
            print(f"  Visit: http://127.0.0.1:{_port}/admin/login  (webadmin / WebAdmin0!)")

        from werkzeug.serving import run_simple
        run_simple(
            addr, _port, application,
            use_reloader=debug and not wsgi_mode,
            use_debugger=debug and not wsgi_mode,
        )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wsCmd",
        description="MultiTaskWS platform management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 wsCmd.py --setup
  python3 wsCmd.py --setup --reset
  python3 wsCmd.py --start
  python3 wsCmd.py --start --wsgi
  python3 wsCmd.py --start --port 8080 --debug
""",
    )

    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--setup", action="store_true",
                      help="Interactive platform setup (writes ~/.MultiTaskWS/MultiTaskWS_config.json)")
    mode.add_argument("--start", action="store_true",
                      help="Start the full WSGI dispatcher")

    # --setup options
    ap.add_argument("--reset", action="store_true",
                    help="[--setup] Delete config + adminTracker DB before setup")

    # --start options
    ap.add_argument("--local", action="store_true",
                    help="[--start] Local Werkzeug dev server (default, implied by --start)")
    ap.add_argument("--wsgi", action="store_true",
                    help="[--start] WSGI mode: no reloader/debugger (mirrors PA stack)")
    ap.add_argument("--addr", default="127.0.0.1", metavar="IP",
                    help="[--start] Bind address (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=None,
                    help="[--start] Port (default: 8080)")
    ap.add_argument("--debug", action="store_true",
                    help="[--start] Enable reloader + debugger (ignored in --wsgi mode)")

    return ap


def main():
    args = _build_parser().parse_args()
    ws   = WsCmd()

    if args.setup:
        ws.setup(reset=args.reset)
    else:
        ws.start(
            wsgi_mode=args.wsgi,
            addr=args.addr,
            port=args.port,
            debug=args.debug,
        )


if __name__ == "__main__":
    main()

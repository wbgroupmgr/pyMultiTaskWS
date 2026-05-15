"""
multitrack/auth.py
==================
Platform-level authentication module for MultiTrack Web Platform.

Provides GPG-encrypted user DB management, Flask route factory
(/login, /logout, /register), and the @login_required decorator.
Tracker apps import and configure this module — they do not implement
their own auth logic.

Usage in a Tracker's wsgi.py or app factory
────────────────────────────────────────────
    from multitrack.auth import make_auth_routes, login_required
    from pathlib import Path

    app = Flask(__name__)
    app.secret_key = os.environ['MY_TRACKER_SECRET_KEY']

    db_path = Path('/home/user/mytracker/Accts/pw.json.gpg')
    make_auth_routes(app, db_path=db_path, tracker_name='My Tracker')

    @app.route('/')
    @login_required
    def home(): ...

Environment variables
─────────────────────
  MULTITRACK_GPG_PASSPHRASE   — GPG symmetric passphrase for the user DB.
                                 Can be overridden per-call via passphrase=.
  (No default — server will refuse to start DB operations if unset.)

GPG encryption
──────────────
  Algorithm : AES-256 symmetric (no key-pair required)
  Passphrase: MULTITRACK_GPG_PASSPHRASE env var
  CLI tool  : gpg (GnuPG 2.x must be on PATH)
  Strategy  : passphrase passed via os.pipe fd (not CLI args — invisible in ps)
  Write     : atomic encrypt → .tmp → rename over .gpg

User DB schema (one JSON object per user)
─────────────────────────────────────────
    {
      "username":   "jsmith",
      "password":   "<sha256 hex>",
      "full_name":  "Jane Smith",
      "phone":      "512-555-0100",
      "role":       "member",
      "created_at": "2026-05-15T10:00:00",
      "notes":      ""          ← optional; wbgadminWS stores SECRET_KEY here
    }
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Callable, List, Optional

from flask import (
    Flask, flash, redirect, render_template, request, session, url_for,
)

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_ROLES: List[str] = ["member", "llcManager", "bookkeeper", "accountant"]

_GPG_PASSPHRASE_ENV = "MULTITRACK_GPG_PASSPHRASE"

# Package-bundled templates (Tracker may override via its own template folder).
_TMPL_DIR = Path(__file__).resolve().parent / "templates"


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ── GPG passphrase ────────────────────────────────────────────────────────────

def get_passphrase(passphrase: Optional[str] = None) -> str:
    """Return passphrase arg or read from env; raise RuntimeError if missing."""
    pp = passphrase or os.environ.get(_GPG_PASSPHRASE_ENV, "")
    if not pp:
        raise RuntimeError(
            f"Environment variable {_GPG_PASSPHRASE_ENV} is not set. "
            "Set it before starting the server."
        )
    return pp


# ── GPG helpers ───────────────────────────────────────────────────────────────

def gpg_decrypt(path: Path, passphrase: str) -> bytes:
    """Decrypt path in-memory. Passphrase via os.pipe (invisible in ps)."""
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, (passphrase + "\n").encode())
        os.close(w_fd);  w_fd = -1
        result = subprocess.run(
            ["gpg", "--batch", "--yes", "--quiet",
             "--passphrase-fd", str(r_fd),
             "--decrypt", str(path)],
            capture_output=True,
            pass_fds=(r_fd,),
        )
    finally:
        if w_fd != -1:
            os.close(w_fd)
        os.close(r_fd)
    if result.returncode != 0:
        raise RuntimeError(
            f"GPG decryption failed for {path.name}: "
            + result.stderr.decode(errors="replace").strip()
        )
    return result.stdout


def gpg_encrypt(plaintext: bytes, out_path: Path, passphrase: str) -> None:
    """Encrypt plaintext bytes with AES-256 and write atomically to out_path."""
    tmp = out_path.with_suffix(".tmp")
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, (passphrase + "\n").encode())
        os.close(w_fd);  w_fd = -1
        result = subprocess.run(
            ["gpg", "--batch", "--yes", "--quiet",
             "--symmetric", "--cipher-algo", "AES256",
             "--passphrase-fd", str(r_fd),
             "--output", str(tmp)],
            input=plaintext,
            capture_output=True,
            pass_fds=(r_fd,),
        )
    finally:
        if w_fd != -1:
            os.close(w_fd)
        os.close(r_fd)
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"GPG encryption failed for {out_path.name}: "
            + result.stderr.decode(errors="replace").strip()
        )
    tmp.replace(out_path)


# ── User DB helpers ───────────────────────────────────────────────────────────

def load_users(db_path: Path, passphrase: Optional[str] = None) -> List[dict]:
    """Decrypt and parse the user DB. Returns [] if file is absent."""
    if not db_path.exists():
        return []
    pp = get_passphrase(passphrase)
    raw = gpg_decrypt(db_path, pp)
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"User DB parse error ({db_path.name}): {exc}") from exc


def save_users(db_path: Path, users: List[dict],
               passphrase: Optional[str] = None) -> None:
    """Serialise users to JSON and encrypt atomically. Plaintext stays in memory."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    pp = get_passphrase(passphrase)
    plaintext = json.dumps(users, indent=2, ensure_ascii=False).encode("utf-8")
    gpg_encrypt(plaintext, db_path, pp)


def find_user(users: List[dict], username: str) -> Optional[dict]:
    """Case-insensitive lookup by username."""
    uname = username.strip().lower()
    return next((u for u in users if u.get("username", "").lower() == uname), None)


# ── Decorator ─────────────────────────────────────────────────────────────────

def login_required(view_func: Callable) -> Callable:
    """
    Redirect unauthenticated requests to /login (preserving ?next=).
    Stack immediately under @app.route:

        @app.route('/dashboard')
        @login_required
        def dashboard(): ...

    Alternatively, use make_auth_routes() which installs a before_request
    guard covering all routes automatically.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper


# ── Route factory ─────────────────────────────────────────────────────────────

def make_auth_routes(
    app: Flask,
    db_path: Path,
    tracker_name: str = "App",
    allowed_roles: Optional[List[str]] = None,
    session_days: int = 30,
    protect_all: bool = True,
) -> None:
    """
    Register /login, /logout, /register on app and optionally install a
    before_request guard that protects every other route automatically.

    Parameters
    ──────────
    app           : Flask instance
    db_path       : Path to the tracker's pw.json.gpg user DB
    tracker_name  : Display name shown in login/register page titles
    allowed_roles : List of valid role strings (default: ALLOWED_ROLES)
    session_days  : Persistent-cookie lifetime when "remember me" is checked
    protect_all   : If True (default), install before_request guard so every
                    route except /login /logout /register is auth-protected.
                    Set False if the Tracker decorates routes individually.
    """
    roles = allowed_roles or ALLOWED_ROLES

    # Make package templates available; Tracker's own templates take priority
    # if its jinja_loader is a ChoiceLoader already set up with its folder first.
    from jinja2 import ChoiceLoader, FileSystemLoader
    pkg_loader = FileSystemLoader(str(_TMPL_DIR))
    existing   = app.jinja_loader
    if existing:
        app.jinja_loader = ChoiceLoader([existing, pkg_loader])
    else:
        app.jinja_loader = pkg_loader

    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(days=session_days))

    _PUBLIC = {"login", "logout", "register", "static"}

    # ── before_request guard ──────────────────────────────────────────────────
    if protect_all:
        @app.before_request
        def _require_login():
            if request.endpoint in _PUBLIC:
                return
            if not session.get("logged_in"):
                if request.path.startswith("/api/"):
                    from flask import jsonify
                    return jsonify({"error": "authentication required"}), 401
                return redirect(url_for("login", next=request.path))

    # ── /login ────────────────────────────────────────────────────────────────
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("logged_in"):
            return redirect(url_for("home"))
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password =  request.form.get("password") or ""
            remember = bool(request.form.get("remember"))
            try:
                users = load_users(db_path)
            except RuntimeError as exc:
                app.logger.error("Login DB error: %s", exc)
                flash("Authentication service unavailable. Contact your administrator.", "error")
                return render_template("login.html", tracker_name=tracker_name)
            user = find_user(users, username)
            if user and user.get("password") == hash_password(password):
                session.clear()
                session["logged_in"] = True
                session["username"]  = user["username"]
                session["full_name"] = user.get("full_name", username)
                session["role"]      = user.get("role", "member")
                if remember:
                    session.permanent = True
                next_url = request.form.get("next") or request.args.get("next") or ""
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect(url_for("home"))
            flash("Invalid username or password.", "error")
        return render_template("login.html", tracker_name=tracker_name)

    # ── /logout ───────────────────────────────────────────────────────────────
    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been signed out.", "info")
        return redirect(url_for("login"))

    # ── /register ─────────────────────────────────────────────────────────────
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if session.get("logged_in"):
            return redirect(url_for("home"))
        errors: dict = {}
        form:   dict = {}
        if request.method == "POST":
            form = {
                "full_name": (request.form.get("full_name") or "").strip(),
                "phone":     (request.form.get("phone")     or "").strip(),
                "role":      (request.form.get("role")      or "").strip(),
                "username":  (request.form.get("username")  or "").strip(),
                "password":  (request.form.get("password")  or ""),
                "password2": (request.form.get("password2") or ""),
            }
            if not form["full_name"]:
                errors["full_name"] = "Full name is required."
            if not form["phone"]:
                errors["phone"] = "Phone number is required."
            if form["role"] not in roles:
                errors["role"] = "Choose a valid role."
            if not form["username"] or len(form["username"]) < 3:
                errors["username"] = "Username must be at least 3 characters."
            if not form["password"] or len(form["password"]) < 6:
                errors["password"] = "Password must be at least 6 characters."
            elif form["password"] != form["password2"]:
                errors["password2"] = "Passwords do not match."
            if not errors:
                try:
                    users = load_users(db_path)
                except RuntimeError as exc:
                    app.logger.error("Register DB read error: %s", exc)
                    flash("Registration service unavailable.", "error")
                    return render_template("register.html", roles=roles,
                                           errors={}, form=form,
                                           tracker_name=tracker_name)
                if find_user(users, form["username"]):
                    errors["username"] = "That username is already taken."
            if not errors:
                users.append({
                    "username":   form["username"],
                    "password":   hash_password(form["password"]),
                    "full_name":  form["full_name"],
                    "phone":      form["phone"],
                    "role":       form["role"],
                    "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                })
                try:
                    save_users(db_path, users)
                except RuntimeError as exc:
                    app.logger.error("Register DB write error: %s", exc)
                    flash("Could not save account. Contact your administrator.", "error")
                    return render_template("register.html", roles=roles,
                                           errors={}, form=form,
                                           tracker_name=tracker_name)
                flash(f"Account created for {form['full_name']}. Please sign in.", "success")
                return redirect(url_for("login"))
        return render_template("register.html", roles=roles,
                                errors=errors, form=form,
                                tracker_name=tracker_name)

# MultiTrack Web Platform — Architecture & Setup Guide

---

## 1. Concept & Architecture

### 1.1 What Is MultiTrack?

**MultiTrack** is a web platform where multiple independent task-focused
applications — called **Trackers** — coexist under a single web server
host. Each Tracker is fully self-contained: its own codebase, its own
user database, its own URL namespace, and its own authentication domain.
The platform scales horizontally — adding a new Tracker requires no
changes to existing ones.

The `pyMultiTaskWS` package provides the **platform-level core services**:

| Service | Module | Purpose |
|---------|--------|---------|
| Dispatcher | `multitrack_wsgi.py` | Routes requests by URL prefix to the correct Tracker |
| Auth | `multitrack/auth.py` | GPG-encrypted user DB, Flask login routes, `login_required` decorator |
| Templates | `multitrack/templates/` | Generic `login.html` and `register.html` (Tracker may override) |
| Smoke-test | `trackerWeb/` | Minimal reference Tracker — confirms the platform is running |
| Setup | `setup/setupWebServerCmd.py` | Interactive one-shot PA setup per Tracker |
| Seed | `setup/init_userdb.py` | CLI seed tool for Tracker user DBs |

This pattern maps to standard enterprise web-design concepts:

| MultiTrack term | Standard equivalent |
|---|---|
| **Platform** | Application hub / hosting container |
| **Dispatcher** | WSGI router / `DispatcherMiddleware` |
| **Tracker** | Mounted sub-application / bounded context |
| **Tracker Entry Point** | WSGI callable (`wsgi.py`) |
| **Mount point** | URL prefix / `APPLICATION_ROOT` |
| **Tracker ID** | Application namespace (URL slug) |

---

### 1.2 Component Hierarchy

```
pyMultiTaskWS (DispatcherMiddleware)
│   multitrack_wsgi.py routes requests by URL prefix.
│   Unmatched prefixes return 404.
│
├── /web  ──────────────→  TrackerWeb  (platform smoke-test)
│                              └── Flask app  ←  trackerWeb/wsgi.py
│
├── /llc  ──────────────→  LLC Tracker  (WBGroup LLC Editor)
│                              └── Flask app  ←  wsgi.py  [separate repo]
│
└── /trackHealth  ──────→  Health Tracker  (future)
                               └── Flask app  ←  wsgi.py  [separate repo]
```

**Request flow:**

```
Browser → WSGI server
       → multitrack_wsgi.py  (strips prefix, sets SCRIPT_NAME)
       → Tracker Flask app   (sees only its own sub-path)
       → Response            (Flask reconstructs full URLs via SCRIPT_NAME)
```

---

### 1.3 URL Namespace

Every Tracker owns a distinct URL subtree:

```
https://<host>/<TrackerID>/
    ├── <TrackerID>/login       ← login page
    ├── <TrackerID>/            ← home (requires login)
    ├── <TrackerID>/view/<...>  ← Tracker views
    └── <TrackerID>/api/<...>   ← Tracker API (returns JSON 401 if not logged in)
```

The `<TrackerID>` must be globally unique across the Platform and is used
as both the URL mount point and the directory name on disk.

---

### 1.4 Authentication Model

Each Tracker maintains its **own independent user database**
(`Accts/pw.json.gpg`). Users registered in one Tracker have no access to
any other. There is no cross-Tracker single sign-on.

`multitrack.auth` provides:

- `make_auth_routes(app, db_path, tracker_name, ...)` — registers
  `/login`, `/logout`, `/register` and installs a `before_request` guard
  protecting all other routes automatically.
- `login_required` — decorator for per-route protection (alternative to
  the global guard).
- `load_users` / `save_users` / `find_user` — GPG-encrypted JSON DB helpers.
- `hash_password` — SHA-256 hex digest.

---

## 2. Package Layout

```
pyMultiTaskWS/
│
├── setupWebServerCmd.py        ← One-shot interactive PA setup (run this first)
├── multitrack_wsgi.py          ← Dispatcher (PA imports this; runnable locally too)
│
├── multitrack/                 ← Platform core package
│   ├── __init__.py
│   ├── auth.py                 ← Auth module — import in every Tracker
│   └── templates/
│       ├── login.html          ← Generic login page (uses tracker_name + url_for)
│       └── register.html       ← Generic register page
│
├── trackerWeb/                 ← Platform smoke-test Tracker (TrackerID: web)
│   ├── __init__.py
│   ├── app.py                  ← TrackerWebApp (Flask app class)
│   ├── wsgi.py                 ← WSGI entry point; auto-seeds webadmin user
│   ├── Accts/                  ← pw.json.gpg lives here (gitignored)
│   └── templates/
│       └── home.html           ← Status dashboard (platform badge, session, runtime)
│
├── setup/
│   ├── __init__.py
│   ├── setupWebServerCmd.py    ← Interactive per-Tracker PA setup script
│   └── init_userdb.py          ← CLI seed tool for any Tracker user DB
│
└── docs/
    └── design_webserver.md     ← This file
```

---

## 3. Local Setup & Smoke Test

Use this section to verify the platform works on a local machine before
deploying to PythonAnywhere.

### 3.1 Prerequisites

| Requirement | Check |
|------------|-------|
| Python 3.10+ | `python3 --version` |
| GnuPG 2.x | `gpg --version` |
| git | `git --version` |

### 3.2 Clone and Install

```bash
git clone https://github.com/wbgroupmgr/pyMultiTaskWS.git
cd pyMultiTaskWS
pip install flask werkzeug
```

No package installation is needed — `multitrack` and `trackerWeb` are
imported directly from the repo root, which `multitrack_wsgi.py` and
`trackerWeb/wsgi.py` both add to `sys.path` automatically.

### 3.3 Set the GPG Passphrase

The platform requires `MULTITRACK_GPG_PASSPHRASE` to encrypt/decrypt user
databases. For local testing any string of 12+ characters works — it
only needs to be consistent within a single run (the DB is created and
read with the same passphrase).

```bash
export MULTITRACK_GPG_PASSPHRASE="localtest1234"
```

> On Windows PowerShell: `$env:MULTITRACK_GPG_PASSPHRASE = "localtest1234"`

### 3.4 Run Option A — TrackerWeb Standalone

The simplest path: runs only TrackerWeb, no dispatcher, mounted at `/`.

> **Local machines only.** Never run with `python` on PythonAnywhere —
> PA imports the file automatically. See Section 4.

```bash
python trackerWeb/wsgi.py
```

```
Starting TrackerWeb standalone on http://127.0.0.1:8081
Default credentials: webadmin / WebAdmin0!
```

Visit **http://127.0.0.1:8081/login** and sign in.

On first run `trackerWeb/wsgi.py` auto-seeds `trackerWeb/Accts/pw.json.gpg`
with the default account. No separate setup step is needed.

### 3.5 Run Option B — Full Dispatcher (recommended)

Runs the `DispatcherMiddleware` exactly as it runs on PA. TrackerWeb is
mounted at `/web`.

> **Local machines only.** On PythonAnywhere, the PA WSGI server imports
> `multitrack_wsgi.py` directly — running it with `python` will fail with
> "Address already in use" because PA's server already owns those ports.

```bash
python multitrack_wsgi.py
```

```
MultiTrack dispatcher on http://127.0.0.1:8080
  /web  → TrackerWeb  (webadmin / WebAdmin0!)
```

Visit **http://127.0.0.1:8080/web/login** and sign in.

### 3.6 What to Verify on the Home Page

After signing in, the TrackerWeb home page (`/web/`) shows a status
dashboard. Check each row:

| Card | What to look for |
|------|-----------------|
| **Platform Status** | "MultiTrack Web Platform — Online" badge with pulsing dot |
| **Tracker → Mount point** | `/web` (Option B) or `/` (Option A standalone) — confirms `SCRIPT_NAME` is set correctly by the dispatcher |
| **Tracker → User DB** | Path to `trackerWeb/Accts/pw.json.gpg` |
| **Session** | Your username, role (`member`), and whether the session is persistent |
| **Runtime → SCRIPT_NAME** | `/web` in Option B; `(none — standalone)` in Option A |
| **Runtime → Host** | `127.0.0.1:5000` |

> **Key test:** If the Mount point shows `/web` (not `/`), the dispatcher
> is stripping the prefix and setting `SCRIPT_NAME` correctly. All
> `url_for()` calls will generate paths prefixed with `/web/`.

### 3.7 Stopping the Server

`Ctrl-C` in the terminal. The user DB (`pw.json.gpg`) persists between
runs — delete `trackerWeb/Accts/pw.json.gpg` to reset to a clean state.

---

## 4. PythonAnywhere Deployment

> PA custom plan assumed (multiple web apps).
> **Web App 1** = MultiTrack Platform.

### 4.1 PA Directory Layout

```
/home/<pa-user>/
│
├── multitrack_wsgi.py          ← Platform WSGI file (PA points here)
│
├── pyMultiTaskWS/              ← This repo (platform core)
│   ├── multitrack/
│   ├── trackerWeb/
│   └── setup/
│
├── llc/                        ← TrackerID directory
│   └── LLC-WB-Group/           ← Tracker git repo
│       └── pages/AccountingData/
│           ├── Accts/pw.json.gpg       ← Tracker user DB (not in git)
│           └── Notebooks/              ← sys.path root
│               └── wsgi.py             ← Tracker entry point
│
└── trackHealth/                ← future TrackerID directory
    └── <repo>/wsgi.py
```

**Convention:** `TrackerID == directory name under /home/<pa-user>/`

---

### 4.2 Step 0 — PA Dashboard: Create the Web App

1. Sign in to [pythonanywhere.com](https://www.pythonanywhere.com).
2. **Dashboard → Web tab → Add a new web app**
   - Framework: **Manual configuration**
   - Python version: **3.10**
3. In the **Code** section:
   - **WSGI configuration file** → `/home/<pa-user>/multitrack_wsgi.py`
   - **Source code** → `/home/<pa-user>/`

---

### 4.3 Step 1 — Bash Console: Clone the Platform Repo

Open a **Bash console** (Dashboard → Consoles → Bash).

```bash
cd ~
git clone https://github.com/wbgroupmgr/pyMultiTaskWS.git
```

---

### 4.4 Step 2 — Run the Platform Setup Script

```bash
cd ~/pyMultiTaskWS
python3.10 setupWebServerCmd.py
```

The script runs interactively:

| Step | Action |
|------|--------|
| 1 | Prompts for `MULTITRACK_GPG_PASSPHRASE` (min 12 chars, confirmed) |
| 2 | Installs `flask` and `werkzeug` via pip |
| 3 | Seeds `trackerWeb/Accts/pw.json.gpg` with `webadmin / WebAdmin0!` |
| 4 | Generates `WEB_SECRET_KEY`; stores it in `pw.json.gpg` under `_wsadmin.notes` |
| 5 | Prints the complete ready-to-paste `~/multitrack_wsgi.py` content |

**Copy the printed WSGI block** — you need it in Step 3.

---

### 4.5 Step 3 — Create `~/multitrack_wsgi.py`

```bash
nano ~/multitrack_wsgi.py
```

Paste the block printed by the setup script (credentials are already
filled in). It will look like:

```python
import sys, os
from pathlib import Path
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# ── pyMultiTaskWS root ────────────────────────────────────────────────────────
_pkg = '/home/<pa-user>/pyMultiTaskWS'
if _pkg not in sys.path:
    sys.path.insert(0, _pkg)

# ── TrackerWeb ────────────────────────────────────────────────────────────────
os.environ.setdefault('MULTITRACK_GPG_PASSPHRASE', '<your-passphrase>')
os.environ.setdefault('WEB_SECRET_KEY',            '<generated-key>')
from trackerWeb.wsgi import application as web_app

# ── LLC Tracker (uncomment after running LLC setup) ───────────────────────────
# os.environ.setdefault('LLC_GPG_PASSPHRASE', '<llc-passphrase>')
# os.environ.setdefault('LLC_SECRET_KEY',     '<llc-secret-key>')
# sys.path.insert(0, '/home/<pa-user>/llc/LLC-WB-Group/pages/AccountingData/Notebooks')
# from wsgi import application as llc_app

# ── Dispatcher ────────────────────────────────────────────────────────────────
application = DispatcherMiddleware(NotFound(), {
    '/web': web_app,
    # '/llc': llc_app,
})
```

Lock down the file — it contains plaintext credentials:

```bash
chmod 600 ~/multitrack_wsgi.py
```

> **Never commit `~/multitrack_wsgi.py` to any git repo.**

---

### 4.6 Step 4 — Reload and Test

1. PA **Web tab → Reload** button.
2. Visit `https://<pa-user>.pythonanywhere.com/web/login`
   - Sign in: `webadmin / WebAdmin0!`
   - Verify the **Mount point** row on the home page shows `/web`

If the mount point shows `/web` (not `/`), the dispatcher is working
correctly.

---

### 4.7 Adding the LLC Tracker

Once TrackerWeb confirms the platform is running, add the LLC Tracker:

```bash
# 1. Clone the LLC repo
mkdir -p ~/llc
cd ~/llc
git clone https://github.com/wbgroupmgr/LLC-WB-Group.git

# 2. Run the LLC setup script (installs deps, seeds user DB, prints credentials)
cd ~/llc/LLC-WB-Group/pages/AccountingData/Notebooks
pip install --user flask pandas numpy pypdf werkzeug deepdiff
python3.10 setupWebServerCmd.py

# 3. Edit ~/multitrack_wsgi.py — uncomment the LLC block, paste printed credentials

# 4. PA Web tab → Reload
```

After reload, visit `https://<pa-user>.pythonanywhere.com/llc/login`.

---

### 4.8 Adding Any Future Tracker

```bash
# 1. Clone into its TrackerID directory
mkdir -p ~/trackHealth
cd ~/trackHealth
git clone https://github.com/<org>/<health-repo>.git

# 2. Run that Tracker's setup script
cd ~/trackHealth/<repo>/...
python3.10 setupWebServerCmd.py   # or setup/setupWebServerCmd.py

# 3. Edit ~/multitrack_wsgi.py — add the printed block + mount

# 4. PA Web tab → Reload
```

---

### 4.9 Updating a Tracker

```bash
cd ~/<trackerid>/<repo>
git pull origin main
# PA Web tab → Reload  (no WSGI file changes needed)
```

---

## 5. Tracker Developer Guidelines

### 5.1 Required: `wsgi.py` Entry Point

Every Tracker exposes a `wsgi.py` at its `sys.path` root that adds its
package root to `sys.path` and exposes `application` — the Flask app.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mytracker.app import MyTrackerApp

_app_obj    = MyTrackerApp(...)
application = _app_obj.app
```

`MyTrackerApp.__init__` calls `make_auth_routes(self.app, db_path, ...)`.
See `trackerWeb/app.py` for the complete reference pattern.

---

### 5.2 Required: `url_for()` in Templates — No Hardcoded Paths

When mounted via `DispatcherMiddleware`, WSGI sets `SCRIPT_NAME`
(e.g. `/llc`). `url_for()` picks this up automatically; hardcoded strings
do not.

| Pattern | Mounted at `/llc` | Correct? |
|---|---|---|
| `action="/login"` | Posts to `/login` (wrong) | ✗ |
| `href="/logout"` | Navigates to `/logout` (wrong) | ✗ |
| `action="{{ url_for('login') }}"` | `/llc/login` | ✓ |
| `href="{{ url_for('logout') }}"` | `/llc/logout` | ✓ |
| `window.location.href = "/logout"` | `/logout` (wrong) | ✗ |
| `window.location.href = "{{ url_for('logout') }}"` | `/llc/logout` | ✓ |

The platform templates (`multitrack/templates/`) already use `url_for()`
throughout. All Tracker-specific templates must follow the same rule.

---

### 5.3 Required: `multitrack.auth` Integration

```python
import os, secrets
from pathlib import Path
from multitrack.auth import make_auth_routes

self.app.secret_key = os.environ.get("MYTRACKER_SECRET_KEY", secrets.token_hex(32))

make_auth_routes(
    self.app,
    db_path=Path("/path/to/Accts/pw.json.gpg"),
    tracker_name="My Tracker",
)
```

The `protect_all=True` default installs a `before_request` guard that
protects every route except `login`, `logout`, `register`, and `static`.
API routes under `/api/` get a JSON `{"error": "authentication required"}`
with HTTP 401 instead of a redirect.

---

### 5.4 Required: Isolated User DB

Each Tracker stores its user database at `Accts/pw.json.gpg` within its
own repo directory. Passphrases and secret keys are distinct per Tracker.
Add `**/Accts/*.gpg` to the Tracker's `.gitignore`.

---

### 5.5 Recommended: Tracker ID Convention

- Short, lowercase, URL-safe slug: `llc`, `health`, `finance`, `web`
- Used as: directory name, mount point, and env var prefix (`LLC_`, `HEALTH_`)
- No hyphens; underscores in Python package names

---

## 6. Key Files Reference

| File | Scope | Purpose |
|------|-------|---------|
| `setupWebServerCmd.py` | Platform | One-shot interactive PA setup — run this first |
| `~/multitrack_wsgi.py` | Platform | Dispatcher; mounts Trackers; holds credentials |
| `multitrack/auth.py` | Platform | Shared auth — import in every Tracker |
| `multitrack/templates/login.html` | Platform | Generic login page |
| `multitrack/templates/register.html` | Platform | Generic register page |
| `trackerWeb/wsgi.py` | TrackerWeb | WSGI entry; auto-seeds DB; standalone runnable |
| `trackerWeb/app.py` | TrackerWeb | Reference Tracker implementation |
| `trackerWeb/templates/home.html` | TrackerWeb | Platform status dashboard |
| `setup/setupWebServerCmd.py` | Platform | Interactive per-Tracker PA setup |
| `setup/init_userdb.py` | Platform | CLI user DB seed tool |
| `<tracker>/wsgi.py` | Tracker | WSGI entry point; exposes `application` |
| `<tracker>/Accts/pw.json.gpg` | Tracker | Encrypted user DB (not in git) |
| `<tracker>/requirements.txt` | Tracker | Python dependencies |

---

## 7. Security Notes

| Concern | Approach |
|---------|---------|
| Credentials in WSGI | `~/multitrack_wsgi.py` is owner-readable only (`chmod 600`); never in git |
| GPG passphrase | Per-Tracker env var; passed to `gpg` subprocess via `os.pipe()` fd — invisible in `ps aux` |
| Flask secret key | Generated at setup; stored in `pw.json.gpg` under `_wsadmin.notes` |
| User passwords | SHA-256 hashed; plaintext never written to disk |
| Cross-Tracker isolation | Separate user DBs, separate passphrases, separate Flask secret keys |
| User DB files | `**/Accts/*.gpg` excluded from git via `.gitignore` |

---

## 8. User DB Schema

`Accts/pw.json.gpg` decrypts to a JSON array. Standard user record:

```json
{
  "username":   "admin",
  "password":   "<sha256-hex>",
  "full_name":  "Admin User",
  "phone":      "",
  "role":       "member",
  "created_at": "2026-01-01T00:00:00"
}
```

The `_wsadmin` record stores the Flask secret key (written by
`setupWebServerCmd.py`):

```json
{
  "username":   "_wsadmin",
  "password":   "",
  "full_name":  "webserver admin",
  "role":       "admin",
  "notes":      "<64-char-hex-secret-key>",
  "created_at": "..."
}
```

`multitrack.auth.ALLOWED_ROLES` defines the default valid role strings:
`["member", "llcManager", "bookkeeper", "accountant"]`. Trackers may pass
their own list via `make_auth_routes(allowed_roles=[...])`.

---

## 9. Role Permissions

> **Note:** Permission enforcement is a future implementation item.
> The table defines the intended policy; no role-based restrictions
> are currently active in `multitrack.auth`.

| Role | Views | Fields | DB | Registration |
|------|-------|--------|----|--------------|
| `llcManager` | View All | All | Refresh | New, Delete, Edit |
| `member` | View All | View Only | No Refresh | No access |
| `bookkeeper` | View All | Edit | Session Only | No access |
| `accountant` | View All | View Only | No Refresh | No access |
| `_wsadmin` | View All | View Only | No Refresh | New, Delete, Edit |

- **Views** — which pages/statements the role can access
- **Fields** — read-only vs. editable transaction fields
- **DB** — `Refresh` = can reload/new-session; `Session Only` = working-file edits only; `No Refresh` = read-only
- **Registration** — ability to create/delete/edit accounts in `pw.json.gpg`

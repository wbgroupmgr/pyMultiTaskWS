# MultiTrack Web Platform — Architecture & PythonAnywhere Deployment

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
| Setup | `setup/setupWebServerCmd.py` | Interactive one-shot PA setup per Tracker |
| Seed | `setup/init_userdb.py` | CLI seed tool for Tracker user DBs |

This pattern is standard in enterprise web design under names such as
*application hub*, *sub-application hosting*, or *WSGI application
dispatch*. The MultiTrack terminology maps to those concepts:

| MultiTrack term | Standard web-design equivalent |
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
PythonAnywhere Web App (MultiTrack)
│
└── multitrack_wsgi.py  (DispatcherMiddleware)
    │   Routes incoming requests by URL prefix to the correct Tracker.
    │   Unmatched prefixes return 404.
    │
    ├── /llc  ──────────────→  LLC Tracker  (WBGroup LLC Editor)
    │                              └── Flask app  ←  wsgi.py
    │
    ├── /trackHealth  ──────→  Health Tracker  (future)
    │                              └── Flask app  ←  wsgi.py
    │
    └── /trackFinance  ─────→  Finance Tracker  (future)
                                   └── Flask app  ←  wsgi.py
```

**Request flow:**

```
Browser → PA WSGI server
       → multitrack_wsgi.py (strips prefix, sets SCRIPT_NAME)
       → Tracker Flask app (sees only its own sub-path)
       → Response (Flask reconstructs full URLs via SCRIPT_NAME)
```

---

### 1.3 URL Namespace

Every Tracker owns a distinct URL subtree:

```
https://<host>/<TrackerID>/
    ├── <TrackerID>/login       ← Tracker login page
    ├── <TrackerID>/            ← Tracker home (requires login)
    ├── <TrackerID>/view/<...>  ← Tracker views
    └── <TrackerID>/api/<...>   ← Tracker API
```

The `<TrackerID>` is the mount-point string and must be globally unique
across the Platform. It is also used as the directory name on disk.

---

### 1.4 Authentication Model

Each Tracker maintains its **own independent user database**
(`Accts/pw.json.gpg`). Users registered in one Tracker have no access
to any other. There is no cross-Tracker single sign-on. The
`<TrackerID>/login` page is each Tracker's entry gate.

`multitrack.auth` provides:

- `make_auth_routes(app, db_path, tracker_name, ...)` — registers
  `/login`, `/logout`, `/register` on any Flask app and installs a
  `before_request` guard protecting all other routes automatically.
- `login_required` decorator — for Trackers that prefer per-route auth.
- `load_users` / `save_users` / `find_user` — GPG-encrypted JSON DB helpers.
- `hash_password` — SHA-256 hex digest.

---

## 2. `pyMultiTaskWS` Package Layout

```
pyMultiTaskWS/
│
├── multitrack_wsgi.py          ← Platform dispatcher (copy to ~/multitrack_wsgi.py on PA)
│
├── multitrack/
│   ├── __init__.py
│   ├── auth.py                 ← Platform auth module (used by every Tracker)
│   └── templates/
│       ├── login.html          ← Generic login page (uses tracker_name)
│       └── register.html       ← Generic register page
│
└── setup/
    ├── __init__.py
    ├── setupWebServerCmd.py    ← Interactive one-shot setup per Tracker
    └── init_userdb.py          ← CLI seed tool for a Tracker user DB
```

---

## 3. PythonAnywhere Directory Layout

```
/home/<pa-user>/
│
├── multitrack_wsgi.py          ← Platform WSGI file (PA points here)
│
├── llc/                        ← TrackerID directory
│   └── LLC-WB-Group/           ← Tracker git repo root
│       ├── pages/
│       │   └── AccountingData/
│       │       ├── Accts/
│       │       │   └── pw.json.gpg     ← Tracker user DB (not in git)
│       │       └── Notebooks/          ← sys.path root for this Tracker
│       │           ├── wsgi.py         ← Tracker Entry Point
│       │           └── ...
│       └── requirements.txt
│
├── trackHealth/                ← future TrackerID directory
│   └── <repo>/wsgi.py
│
└── trackFinance/               ← future TrackerID directory
    └── <repo>/wsgi.py
```

**Convention:** `TrackerID == directory name under /home/<pa-user>/`

---

## 4. PythonAnywhere Setup

> PA custom plan assumed: multiple web apps available.
> **Web App 1** = MultiTrack Platform.

---

### 4.1 Step 0 — PA Dashboard: Create the MultiTrack Web App

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com) → sign in.
2. **Dashboard → Web tab → Add a new web app**
   - Framework: **Manual configuration**
   - Python version: **3.10**
3. In the **Code** section:
   - **WSGI configuration file** → change to: `/home/<pa-user>/multitrack_wsgi.py`
   - **Source code** → `/home/<pa-user>/`
4. Leave the page open — you'll paste content in Step 3.

---

### 4.2 Step 1 — Bash Console: Clone Each Tracker Repo

Open a **Bash console** (Dashboard → Consoles → Bash).

```bash
# Create TrackerID dir and clone the Tracker repo
mkdir -p ~/<trackerid>
cd ~/<trackerid>
git clone https://github.com/<org>/<tracker-repo>.git
```

---

### 4.3 Step 2 — Run Tracker Setup

From the Tracker's Notebooks directory:

```bash
python3.10 /path/to/pyMultiTaskWS/setup/setupWebServerCmd.py \
    --tracker-name "My Tracker" \
    --tracker-id   mytracker \
    --db           ~/<trackerid>/<repo>/Accts/pw.json.gpg \
    --notebooks    ~/<trackerid>/<repo>/path/to/notebooks \
    --seed-user    admin \
    --seed-pass    "Admin0Pass!" \
    --seed-role    member \
    --extra-deps   pandas numpy pypdf
```

The script:

| Step | Action |
|------|--------|
| 1 | Prompts for `<TRACKERID>_GPG_PASSPHRASE` (min 12 chars) |
| 2 | Installs pip dependencies |
| 3 | Seeds `pw.json.gpg` with the seed user |
| 4 | Generates `SECRET_KEY`; stores in `pw.json.gpg` under `_wsadmin.notes` |
| 5 | Prints the Tracker block to add to `multitrack_wsgi.py` |

Save the printed output — you need it in Step 3.

---

### 4.4 Step 3 — Create the Platform WSGI File

```bash
nano ~/multitrack_wsgi.py
```

Use the template in `pyMultiTaskWS/multitrack_wsgi.py` and fill in
values printed by the setup script:

```python
import sys, os
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# ── Tracker block (printed by setupWebServerCmd.py) ───────────────────────────
os.environ.setdefault('MYTRACKER_GPG_PASSPHRASE', '<passphrase>')
os.environ.setdefault('MYTRACKER_SECRET_KEY',     '<secret-key>')
sys.path.insert(0, '/home/<pa-user>/<trackerid>/<repo>/path/to/notebooks')
from wsgi import application as mytracker_app

# ── Dispatcher ────────────────────────────────────────────────────────────────
application = DispatcherMiddleware(NotFound(), {
    '/mytracker': mytracker_app,
})
```

> **Security:** `multitrack_wsgi.py` is readable only by your PA account
> (mode 600). This is the only place credentials are stored in plaintext —
> keep it out of any git repo.

---

### 4.5 Step 4 — Reload and Test

1. PA **Web tab → Reload** button.
2. Visit `https://<pa-user>.pythonanywhere.com/<trackerid>/login`
3. Log in with the seed user credentials.

---

### 4.6 Adding a Future Tracker

```bash
# 1. Console: create TrackerID dir, clone, run setup script
mkdir -p ~/trackHealth
cd ~/trackHealth
git clone https://github.com/<org>/<health-repo>.git
python3.10 /path/to/pyMultiTaskWS/setup/setupWebServerCmd.py \
    --tracker-name "Health Tracker" --tracker-id trackHealth ...

# 2. Edit ~/multitrack_wsgi.py — add the printed Tracker block

# 3. PA Web tab → Reload
```

---

### 4.7 Updating a Tracker

```bash
cd ~/<trackerid>/<repo>
git pull origin main
```

Then **PA Web tab → Reload**. No WSGI file changes needed.

---

## 5. Tracker Developer Guidelines

### 5.1 Required: `wsgi.py` Entry Point

Every Tracker repo must expose a `wsgi.py` at its `sys.path` root that
adds its package root to `sys.path` and exposes `application` — the
Flask app WSGI callable.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mytracker.session import init_session
from mytracker.app import AppClass

_session = init_session(...)
_mgmt    = AppClass(_session)
application = _mgmt.app
```

The Tracker's `AppClass.__init__` is responsible for calling
`make_auth_routes(self.app, db_path, tracker_name)` from `multitrack.auth`.

---

### 5.2 Required: Use `url_for()` in Templates — No Hardcoded Paths

When Flask is mounted at a sub-path via `DispatcherMiddleware`, WSGI sets
`SCRIPT_NAME` (e.g. `/llc`). Flask's `url_for()` picks this up and
generates correct absolute URLs. Hardcoded path strings do not.

| Pattern | Mounted at `/llc` result | Correct? |
|---|---|---|
| `action="/login"` | Posts to `/login` (wrong root) | ✗ |
| `href="/logout"` | Navigates to `/logout` (wrong root) | ✗ |
| `action="{{ url_for('login') }}"` | Posts to `/llc/login` | ✓ |
| `href="{{ url_for('logout') }}"` | Navigates to `/llc/logout` | ✓ |
| `window.location.href = "/logout"` | Navigates to `/logout` (JS, wrong) | ✗ |
| `window.location.href = "{{ url_for('logout') }}"` | `/llc/logout` | ✓ |

The generic templates in `multitrack/templates/` already use `url_for()`
throughout. Tracker-specific templates must follow the same convention.

---

### 5.3 Required: `multitrack.auth` Integration

In the Tracker's Flask app constructor:

```python
import os, secrets
from multitrack.auth import make_auth_routes
from pathlib import Path

# Secret key: read from env (set by multitrack_wsgi.py) or generate a random one
self.app.secret_key = os.environ.get("MYTRACKER_SECRET_KEY", secrets.token_hex(32))

# Register /login, /logout, /register and install before_request guard
db_path = Path("/path/to/Accts/pw.json.gpg")
make_auth_routes(self.app, db_path=db_path, tracker_name="My Tracker")
```

The `protect_all=True` default installs a `before_request` guard that
protects every route except `login`, `logout`, `register`, and `static`.
API routes under `/api/` receive a JSON `{"error": "authentication required"}`
with HTTP 401 instead of a redirect.

---

### 5.4 Required: Isolated User DB

Each Tracker stores its user database at `Accts/pw.json.gpg` within its
own repo. Passphrases and secret keys are distinct per Tracker. A user
registered in one Tracker does not exist in another.

---

### 5.5 Recommended: Tracker ID Convention

- Short, lowercase, URL-safe slug: `llc`, `health`, `finance`
- Used consistently as: directory name, mount point, env var prefix
- No hyphens (underscores in Python identifiers)

---

## 6. Key Files Reference

| File | Scope | Purpose |
|------|-------|---------|
| `~/multitrack_wsgi.py` | Platform | Dispatcher config; mounts all Trackers; holds env vars |
| `pyMultiTaskWS/multitrack/auth.py` | Platform | Shared auth module — import in every Tracker |
| `pyMultiTaskWS/multitrack/templates/` | Platform | Generic login/register templates |
| `pyMultiTaskWS/setup/setupWebServerCmd.py` | Platform | Interactive per-Tracker PA setup |
| `pyMultiTaskWS/setup/init_userdb.py` | Platform | CLI user DB seed tool |
| `<tracker>/wsgi.py` | Tracker | WSGI entry point; exposes `application` |
| `<tracker>/Accts/pw.json.gpg` | Tracker | Encrypted user DB (not in git) |
| `<tracker>/requirements.txt` | Tracker | Python dependencies |

---

## 7. Security Notes

| Concern | Approach |
|---------|---------|
| Credentials in WSGI | `multitrack_wsgi.py` is owner-readable only; never committed to git |
| GPG passphrase | Per-Tracker env var; passed to subprocess via `os.pipe()` fd (invisible in `ps aux`) |
| Flask secret key | Generated at setup; stored in `pw.json.gpg` under `_wsadmin.notes` |
| User passwords | SHA-256 hashed; plaintext never written to disk |
| Cross-Tracker isolation | Separate user DBs, separate passphrases, separate Flask secret keys |

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

The `_wsadmin` record stores the Flask secret key:

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

`multitrack.auth.ALLOWED_ROLES` defines the default set of valid role
strings: `["member", "llcManager", "bookkeeper", "accountant"]`. Trackers
may pass their own `allowed_roles` list to `make_auth_routes()`.

---

## 9. Role Permissions

> **Note:** Permission enforcement is a future implementation item.
> The table below defines the intended policy; no role-based restrictions
> are active in `multitrack.auth` currently.

| Role | Views | Fields | DB | Registration |
|------|-------|--------|----|--------------|
| `llcManager` | View All | All | Refresh | New, Delete, Edit |
| `member` | View All | View Only | No Refresh | No access |
| `bookkeeper` | View All | Edit | Session Only | No access |
| `accountant` | View All | View Only | No Refresh | No access |
| `_wsadmin` | View All | View Only | No Refresh | New, Delete, Edit |

**Column definitions:**

- **Views** — which pages/statements the role can access
- **Fields** — read-only vs. editable transaction fields
- **DB** — `Refresh` = can reload/new-session; `Session Only` = working-file edits, no DB write; `No Refresh` = read-only session
- **Registration** — ability to create / delete / edit user accounts in `pw.json.gpg`

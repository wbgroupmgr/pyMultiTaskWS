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
| Platform CLI | `wsCmd.py` | `--setup` (config + DB seed) and `--start` (full dispatcher) |
| Dispatcher | `wsgi.py` | PA entry point — imports `WsCmd().make_application()` |
| Auth | `multitrack/auth.py` | GPG-encrypted user DB, Flask login routes, `login_required` |
| Templates | `multitrack/templates/` | Generic `login.html` and `register.html` (Tracker may override) |
| Admin | `adminTracker/` | Platform administration Tracker — tracker index + login |
| Registry | `adminTracker/registry.py` | Tracker list injected by `make_application()`; displayed on home page |

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

### 1.2 wsCmd.py Pattern — Platform and Per-Tracker

Every level of the platform has exactly one `wsCmd.py`:

| File | Scope | `--setup` | `--start` |
|------|-------|-----------|-----------|
| `wsCmd.py` | **Platform** | Interactive setup: passphrase, deps, adminTracker DB seed, write `~/.MultiTaskWS/MultiTaskWS_config.json` | Full WSGI dispatcher (all Trackers via DispatcherMiddleware) |
| `adminTracker/wsCmd.py` | **AdminTracker** | Reseed adminTracker user DB (reads passphrase from platform config) | AdminTracker standalone, no dispatcher prefix |
| `<tracker>/wsCmd.py` | **Tracker** | Tracker-specific setup (reads passphrase from platform config) | Tracker standalone |

**Typical workflow:**

```bash
# 1. First time setup (platform level):
python3 wsCmd.py --setup

# 2. Start full dispatcher locally:
python3 wsCmd.py --start

# 3. Start individual Tracker for dev:
python3 adminTracker/wsCmd.py --start

# 4. Reseed a Tracker's user DB:
python3 adminTracker/wsCmd.py --setup --reset
```

---

### 1.3 Component Hierarchy

```
pyMultiTaskWS (DispatcherMiddleware — built by WsCmd.make_application())
│   wsgi.py → WsCmd().make_application()   (PA entry point)
│   wsCmd.py --start                        (local entry point)
│
├── /admin  ─────────────→  AdminTracker  (platform administration)
│                               └── Flask app  ←  adminTracker/wsgi.py
│                               └── Home page shows all mounted Trackers
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
       → wsgi.py  (imports make_application())
       → DispatcherMiddleware  (strips prefix, sets SCRIPT_NAME)
       → Tracker Flask app     (sees only its own sub-path)
       → Response              (Flask reconstructs full URLs via SCRIPT_NAME)
```

---

### 1.4 Platform Config — `~/.MultiTaskWS/MultiTaskWS_config.json`

`wsCmd.py --setup` writes the platform config to `~/.MultiTaskWS/`. This file holds:

```json
{
  "WEB_GPG_PASSPHRASE": "...",
  "WEB_SECRET_KEY": "...",
  "WebServer": "Host_wbgroup",
  "Trackers": [ ... ],
  "adminTracker": {
    "APP_GPG_PASSPHRASE": "<master>_adminTracker",
    "WEB_SECRET_KEY": "..."
  }
}
```

Each Tracker entry in `Trackers` is used to:
- Populate `adminTracker.registry.TRACKERS` (shown on the admin home page)
- Mount the Tracker's Flask app in the dispatcher

External Trackers (not built into this repo) carry `sys_path` and a `stanza_key`.
Their credentials live in their own top-level stanza — same pattern as `adminTracker`:

```json
{
  "Trackers": [
    {
      "name":        "PropRental Tracker",
      "mount":       "/llc",
      "url":         "/llc/login",
      "description": "W&B Group LLC — double-entry ledger & IRS forms",
      "status":      "online",
      "sys_path":    "/home/wbgroup/llc/LLC-WB-Group/pages/AccountingData/Notebooks",
      "stanza_key":  "llc"
    }
  ],
  "llc": {
    "LLC_GPG_PASSPHRASE": "<master>_llc",
    "LLC_SECRET_KEY":     "<tracker-specific-random>"
  }
}
```

`make_application()` reads `cfg["llc"]`, injects those env vars, adds `sys_path` to
`sys.path`, then imports `wsgi.py` from that root via `importlib.util.spec_from_file_location`.
`stanza_key` defaults to the mount slug (`llc`) if omitted.

File is `chmod 600` — owner-readable only. Never committed to git.

---

### 1.5 URL Namespace

Every Tracker owns a distinct URL subtree:

```
https://<host>/<TrackerID>/
    ├── <TrackerID>/login       ← login page
    ├── <TrackerID>/            ← home (requires login)
    ├── <TrackerID>/view/<...>  ← Tracker views
    └── <TrackerID>/api/<...>   ← Tracker API (JSON 401 if not logged in)
```

The `<TrackerID>` must be globally unique across the Platform and matches the `mount` value in the config (e.g., `admin`, `llc`, `health`).

---

### 1.6 Authentication Model

Each Tracker maintains its **own independent user database**
(`Accts/pw.json.gpg`). Users registered in one Tracker have no access to
any other. There is no cross-Tracker single sign-on.

`multitrack.auth` provides:

- `make_auth_routes(app, db_path, tracker_name, ...)` — registers
  `/login`, `/logout`, `/register` and installs a `before_request` guard.
- `login_required` — decorator for per-route protection.
- `load_users` / `save_users` / `find_user` — GPG-encrypted JSON DB helpers.
- `hash_password` — SHA-256 hex digest.

Each Tracker uses its own `APP_GPG_PASSPHRASE` (derived as `<master>_<stanza_key>`) for its user DB.

---

## 2. Package Layout

```
pyMultiTaskWS/
│
├── wsCmd.py                    ← Platform CLI: --setup and --start
├── wsgi.py                     ← PA entry point (thin — calls WsCmd().make_application())
│
├── multitrack/                 ← Platform core package
│   ├── __init__.py
│   ├── auth.py                 ← Auth module — import in every Tracker
│   └── templates/
│       ├── login.html          ← Generic login page (uses tracker_name + url_for)
│       └── register.html       ← Generic register page
│
├── adminTracker/               ← Platform administration Tracker (TrackerID: admin)
│   ├── __init__.py
│   ├── registry.py             ← Tracker list; populated by make_application() before import
│   ├── app.py                  ← AdminTrackerApp (Flask app class)
│   ├── wsgi.py                 ← WSGI entry point; auto-seeds webadmin user
│   ├── wsCmd.py                ← Tracker-level CLI: --setup (DB reseed) and --start (standalone)
│   ├── Accts/                  ← pw.json.gpg lives here (gitignored)
│   └── templates/
│       └── home.html           ← Tracker index — lists all registered apps + status
│
└── docs/
    └── design_webserver.md     ← This file
```

---

## 3. Local Setup & Smoke Test

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
python3 wsCmd.py --setup
```

The `--setup` command installs Flask and Werkzeug, seeds the adminTracker user DB,
and writes `~/.MultiTaskWS/MultiTaskWS_config.json`.

### 3.3 Start Locally

> **Prerequisite:** run `python3 wsCmd.py --setup` once before starting (see §3.2).

**Option A — Full dispatcher (recommended):**

```bash
python3 wsCmd.py --start
```

```
  MultiTaskWS — Local Start  (http://127.0.0.1:8080)
  /admin     → AdminTracker
```

Visit **http://127.0.0.1:8080/admin/login** — sign in: `webadmin / WebAdmin0!`

**Option B — WSGI mode (mirrors PA stack, no reloader):**

```bash
python3 wsCmd.py --start --wsgi
```

**Option C — AdminTracker standalone only (for tracker dev):**

```bash
python3 adminTracker/wsCmd.py --start
```

Visit **http://127.0.0.1:8081/login** — mounted at `/` (no prefix).

### 3.4 What to Verify on the Home Page

After signing in at `/admin/`, the AdminTracker home page shows:

| Card | What to look for |
|------|-----------------|
| **Platform Status** | "MultiTrack Web Platform — Online" badge with pulsing dot |
| **Tracker Apps** | List of all registered Trackers with name, description, mount, Open link |
| **Runtime → Mount point** | `/admin` (dispatcher mode) or `(none — standalone)` |

> **Key test:** Mount point `/admin` confirms `SCRIPT_NAME` is set correctly by the dispatcher.

### 3.5 Stopping the Server

`Ctrl-C` in the terminal. The user DB persists between runs — use
`python3 adminTracker/wsCmd.py --setup --reset` to reset to a clean state.

---

## 4. PythonAnywhere Deployment

> PA custom plan assumed. **Web App 1** = MultiTrack Platform.

### 4.1 PA Directory Layout

```
/home/wbgroup/
│
├── pyMultiTaskWS/              ← This repo
│   ├── wsCmd.py                ← Platform CLI
│   ├── wsgi.py                 ← PA WSGI entry point (point PA here)
│   ├── multitrack/
│   └── adminTracker/
│
├── llc/                        ← TrackerID directory
│   └── LLC-WB-Group/
│       └── pages/AccountingData/Notebooks/
│           └── wsgi.py         ← LLC Tracker entry point
│
└── ~/.MultiTaskWS/
    └── MultiTaskWS_config.json  ← Platform config (chmod 600, not in git)
```

**Convention:** `TrackerID == mount point slug == directory name under /home/wbgroup/`

---

### 4.2 Step 0 — PA Dashboard: Create the Web App

1. Sign in to [pythonanywhere.com](https://www.pythonanywhere.com).
2. **Dashboard → Web tab → Add a new web app**
   - Framework: **Manual configuration**
   - Python version: **3.10**
3. In the **Code** section:
   - **WSGI configuration file** → `/home/wbgroup/pyMultiTaskWS/wsgi.py`
   - **Source code** → `/home/wbgroup/pyMultiTaskWS/`

---

### 4.3 Step 1 — Clone the Platform Repo

Open a **Bash console** (Dashboard → Consoles → Bash).

```bash
cd ~
git clone https://github.com/wbgroupmgr/pyMultiTaskWS.git
```

---

### 4.4 Step 2 — Run Platform Setup

```bash
cd ~/pyMultiTaskWS
python3.10 wsCmd.py --setup
```

| Step | Action |
|------|--------|
| 1 | Prompts for master passphrase → stored as `WEB_GPG_PASSPHRASE` (min 12 chars, confirmed) |
| 2 | Installs `flask` and `werkzeug` via pip |
| 3 | Derives `adminTracker.APP_GPG_PASSPHRASE = <master>_adminTracker`; writes `~/.MultiTaskWS/MultiTaskWS_config.json` |
| 4 | Seeds `adminTracker/Accts/pw.json.gpg` with `webadmin / WebAdmin0!` |

---

### 4.5 Step 3 — Reload and Test

1. PA **Web tab → Reload** button.
2. Visit `https://wbgroup.pythonanywhere.com/admin/login`
   - Sign in: `webadmin / WebAdmin0!`
   - **Tracker Apps** card shows registered Trackers
   - **Runtime → Mount point** shows `/admin`

---

### 4.6 Adding an External Tracker

> **Prerequisite**: the tracker repo must satisfy the Tracker Repo Contract (see §5.0).

**Step 1 — Clone the tracker repo on PA**

```bash
mkdir -p ~/<trackerid> && cd ~/<trackerid>
git clone <tracker-repo-url>
```

**Step 2 — Install the tracker's dependencies**

```bash
pip3.10 install --user <tracker-specific-packages>
```

**Step 3 — Run the tracker's own setup**

```bash
cd ~/<trackerid>/<repo>/<tracker-sys-path-root>
python3.10 wsCmd.py --setup
```

This seeds the tracker's `Accts/pw.json.gpg` and writes its stanza to
`~/.MultiTaskWS/MultiTaskWS_config.json`.

**Step 4 — Register the tracker in the platform config**

Add a Tracker entry to `~/.MultiTaskWS/MultiTaskWS_config.json`:

```json
{
  "Trackers": [
    { "...existing entries..." },
    {
      "name":        "<Tracker display name>",
      "mount":       "/<trackerid>",
      "url":         "/<trackerid>/login",
      "description": "<one-line description>",
      "status":      "online",
      "sys_path":    "/home/wbgroup/<trackerid>/<repo>/<root>",
      "stanza_key":  "<trackerid>"
    }
  ]
}
```

**Step 5 — PA Web tab → Reload**

Visit `https://wbgroup.pythonanywhere.com/<trackerid>/login`.

---

#### Worked example: PropRental Tracker

```bash
# Step 1 — clone
mkdir -p ~/llc && cd ~/llc
git clone https://github.com/wbgroupmgr/LLC-WB-Group.git

# Step 2 — dependencies
pip3.10 install --user flask pandas numpy pypdf werkzeug deepdiff

# Step 3 — tracker setup
cd ~/llc/LLC-WB-Group/pages/AccountingData/Notebooks
python3.10 wsCmd.py --setup

# Step 4 — add to MultiTaskWS_config.json:
# {
#   "name": "PropRental Tracker", "mount": "/llc", "url": "/llc/login",
#   "description": "W&B Group LLC — double-entry ledger & IRS forms",
#   "status": "online",
#   "sys_path": "/home/wbgroup/llc/LLC-WB-Group/pages/AccountingData/Notebooks",
#   "stanza_key": "llc"
# }
# And a "llc" stanza generated by the tracker's wsCmd.py --setup.

# Step 5 — PA Web tab → Reload
```

After reload, visit `https://wbgroup.pythonanywhere.com/llc/login`.

---

### 4.7 Updating a Tracker

```bash
cd ~/<trackerid>/<repo>
git pull origin main
# PA Web tab → Reload  (no WSGI file changes needed)
```

---

## 5. Tracker Developer Guidelines

### 5.0 Tracker Repo Contract — Required at a Glance

The platform cares about exactly four things in a tracker repo:

| Artifact | Location (relative to `sys_path`) | Purpose |
|---|---|---|
| `wsgi.py` | `<sys_path>/wsgi.py` | Exposes module-level `application` (WSGI callable) |
| `wsCmd.py` | `<sys_path>/wsCmd.py` | CLI: `--setup` (DB seed + stanza) and `--start` (standalone) |
| `Accts/pw.json.gpg` | `<sys_path>/Accts/` | GPG-encrypted user DB — gitignored, created by `--setup` |
| Stanza in platform config | `~/.MultiTaskWS/MultiTaskWS_config.json` | Tracker credentials injected as env vars before `wsgi.py` is imported |

Everything else (views, data models, templates, static files) is internal to the tracker.

**The platform integration checklist:**

- [ ] `wsgi.py` exists at `sys_path` root and exposes `application`
- [ ] `wsCmd.py --setup` seeds `Accts/pw.json.gpg` and writes the tracker stanza to the platform config
- [ ] `wsCmd.py --start` runs the tracker standalone (port of your choosing)
- [ ] All Flask templates use `url_for()` — no hardcoded URL paths
- [ ] Flask app calls `make_auth_routes(...)` from `multitrack.auth`
- [ ] `**/Accts/*.gpg` in `.gitignore`

---

### 5.1 Required: `wsgi.py` Entry Point

Every Tracker exposes a `wsgi.py` at its `sys.path` root that exposes `application`.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mytracker.app import MyTrackerApp

_app_obj    = MyTrackerApp(...)
application = _app_obj.app
```

See `adminTracker/app.py` for the complete reference pattern.

---

### 5.2 Required: `wsCmd.py` Per Tracker

Every Tracker has `wsCmd.py` with `--setup` (DB reseed) and `--start` (standalone).
`--setup` reads `APP_GPG_PASSPHRASE` from the tracker's own stanza in
`~/.MultiTaskWS/MultiTaskWS_config.json`. It does **not** prompt for the passphrase
(platform `wsCmd.py --setup` handles that).

---

### 5.3 Required: `url_for()` in Templates — No Hardcoded Paths

| Pattern | Mounted at `/llc` | Correct? |
|---|---|---|
| `action="/login"` | Posts to `/login` (wrong) | ✗ |
| `action="{{ url_for('login') }}"` | `/llc/login` | ✓ |
| `window.location.href = "/logout"` | `/logout` (wrong) | ✗ |
| `window.location.href = "{{ url_for('logout') }}"` | `/llc/logout` | ✓ |

---

### 5.4 Required: `multitrack.auth` Integration

```python
import os, secrets
from pathlib import Path
from multitrack.auth import make_auth_routes

self.app.secret_key = os.environ.get("MYTRACKER_SECRET_KEY", secrets.token_hex(32))
make_auth_routes(self.app, db_path=Path("Accts/pw.json.gpg"), tracker_name="My Tracker")
```

---

### 5.5 Required: Isolated User DB

Each Tracker stores `Accts/pw.json.gpg` within its own repo. Add `**/Accts/*.gpg` to `.gitignore`.

---

### 5.6 Recommended: Tracker ID Convention

- Short, lowercase, URL-safe slug: `admin`, `llc`, `health`
- Matches: directory name, mount point, env var prefix (`LLC_`, `HEALTH_`)

---

## 6. Key Files Reference

| File | Scope | Purpose |
|------|-------|---------|
| `wsCmd.py` | Platform | CLI — `--setup` (platform config) and `--start` (full dispatcher) |
| `wsgi.py` | Platform | PA entry point — thin wrapper around `WsCmd().make_application()` |
| `~/.MultiTaskWS/MultiTaskWS_config.json` | Platform | Credentials + Tracker list (chmod 600, not in git) |
| `multitrack/auth.py` | Platform | Shared auth — import in every Tracker |
| `multitrack/templates/login.html` | Platform | Generic login page |
| `multitrack/templates/register.html` | Platform | Generic register page |
| `adminTracker/registry.py` | AdminTracker | Tracker list — populated by `make_application()`, shown on home |
| `adminTracker/wsgi.py` | AdminTracker | WSGI entry point; auto-seeds webadmin user |
| `adminTracker/app.py` | AdminTracker | `AdminTrackerApp` — Flask class, home page shows tracker list |
| `adminTracker/wsCmd.py` | AdminTracker | Tracker CLI — `--setup` (DB reseed) and `--start` (standalone) |
| `adminTracker/templates/home.html` | AdminTracker | Tracker index — lists all registered apps |
| `<tracker>/wsgi.py` | Tracker | WSGI entry point; exposes `application` |
| `<tracker>/wsCmd.py` | Tracker | Tracker CLI — `--setup` and `--start` |
| `<tracker>/Accts/pw.json.gpg` | Tracker | Encrypted user DB (not in git) |

---

## 7. Security Notes

| Concern | Approach |
|---------|---------|
| Credentials in config | `~/.MultiTaskWS/MultiTaskWS_config.json` is `chmod 600`; never in git |
| GPG passphrase | Per-tracker `APP_GPG_PASSPHRASE` derived from master; passed to `gpg` via `os.pipe()` — invisible in `ps aux` |
| Flask secret key | Generated at setup; stored in platform config |
| User passwords | SHA-256 hashed; plaintext never written to disk |
| Cross-Tracker isolation | Separate user DBs, separate Flask secret keys |
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

The `wbgadminWS` record stores a config pointer:

```json
{
  "username":   "wbgadminWS",
  "password":   "",
  "full_name":  "webserver admin",
  "role":       "member",
  "notes":      "/home/wbgroup/.MultiTaskWS/MultiTaskWS_config.json",
  "created_at": "..."
}
```

`multitrack.auth.ALLOWED_ROLES` default: `["member", "llcManager", "bookkeeper", "accountant"]`.

---

## 9. Role Permissions

> **Note:** Permission enforcement is a future implementation item.

| Role | Views | Fields | DB | Registration |
|------|-------|--------|----|--------------|
| `llcManager` | View All | All | Refresh | New, Delete, Edit |
| `member` | View All | View Only | No Refresh | No access |
| `bookkeeper` | View All | Edit | Session Only | No access |
| `accountant` | View All | View Only | No Refresh | No access |

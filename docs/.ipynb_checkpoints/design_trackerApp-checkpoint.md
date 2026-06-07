# MultiTrack — Tracker App Developer Guide

> This guide is for developers building or integrating a Tracker app into the
> MultiTrack Web Platform. For platform architecture and initial PA setup, see
> [design_webserver.md](design_webserver.md).

---

## 1. What Is a Tracker?

A **Tracker** is a web application whose code is typically found in a GitHub repo. 

- it can run stand alone as its own web server, or
- it can run as a web app within the **MultiTaskWS** web server.

This document describes a tracker app running within a **MultiTaskWS** web server. 

### 1.1. MultiTaskWS Web Application

A **tracker App** is a self-contained Flask web application mounted at a URL prefix
(`/<trackerid>/`) by the MultiTrack dispatcher. Each Tracker:

- Has its own git repo, codebase, and dependencies
- Maintains its own GPG-encrypted user database (`Accts/pw.json.gpg`)
- Uses `multitrack.auth` for login/logout/register routes
- Is registered in `~/.MultiTaskWS/MultiTaskWS_config.json` with a stanza of credentials

The platform injects the tracker's credentials as env vars, adds its root to
`sys.path`, and imports its `wsgi.py` — nothing else is required.

**adminTracker** (built into `pyMultiTaskWS`) is the reference implementation.
Every pattern in this guide is demonstrated there.

### 1.1 Domain Name

The default domain of a tracker is of the form:

- <paDomainID>.pythonanywhere.com/<trackerid>
- where: <paDomainID> is the PA User ID of the PA Web App. 

A custom domain can be set up per tracker such that user could use: 

- <trackerid>.com

---

## 2. Tracker App Repo Contract — Required at a Glance

The platform cares about exactly four things in a tracker app repo:

| Artifact | Location (relative to `sys_path`) | Purpose |
|---|---|---|
| `wsgi.py` | `<sys_path>/wsgi.py` | Exposes module-level `application` (WSGI callable) |
| `wsCmd.py` | `<sys_path>/wsCmd.py` | CLI: `--setup` (DB seed + stanza) and `--start` (standalone) |
| `Accts/pw.json.gpg` | `<sys_path>/Accts/` | GPG-encrypted user DB — gitignored, created by `--setup` |
| Stanza in platform config | `~/.MultiTaskWS/MultiTaskWS_config.json` | Tracker credentials injected as env vars before `wsgi.py` is imported |

Everything else (views, data models, templates, static files) is internal to the tracker app.

**Platform integration checklist:**

- [ ] `wsgi.py` exists at `sys_path` root and exposes `application`
- [ ] `wsCmd.py --setup` seeds `Accts/pw.json.gpg` and writes the tracker stanza to the platform config
- [ ] `wsCmd.py --start` runs the tracker standalone (port of your choosing)
- [ ] All Flask templates use `url_for()` — no hardcoded URL paths
- [ ] Flask app calls `make_auth_routes(...)` from `multitrack.auth`
- [ ] `**/Accts/*.gpg` in `.gitignore`

---

## 3. Tracker App Developer Guidelines

### 3.1 Required: `wsgi.py` Entry Point

Every Tracker App exposes a `wsgi.py` at its `sys.path` root that exposes `application`.

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

### 3.2 Required: `wsCmd.py` Per Tracker App

Every Tracker App has `wsCmd.py` with `--setup` (DB reseed) and `--start` (standalone).
`--setup` reads the tracker's own stanza from `~/.MultiTaskWS/MultiTaskWS_config.json`
and does **not** prompt for a passphrase — the platform `wsCmd.py --setup` handles that.

Minimum stanza written by `wsCmd.py --setup`:

```json
"<trackerid>": {
  "<TRACKER>_GPG_PASSPHRASE": "<master>_<trackerid>",
  "<TRACKER>_SECRET_KEY":     "<random-hex>"
}
```

See `adminTracker/wsCmd.py` for the complete reference implementation.

---

### 3.3 Required: `url_for()` in Templates — No Hardcoded Paths

| Pattern | Mounted at `/llc` | Correct? |
|---|---|---|
| `action="/login"` | Posts to `/login` (wrong) | ✗ |
| `action="{{ url_for('login') }}"` | `/llc/login` | ✓ |
| `window.location.href = "/logout"` | `/logout` (wrong) | ✗ |
| `window.location.href = "{{ url_for('logout') }}"` | `/llc/logout` | ✓ |

The dispatcher sets `SCRIPT_NAME` to the mount prefix. Flask's `url_for()` uses
`SCRIPT_NAME` automatically — hardcoded paths bypass it and break in dispatcher mode.

---

### 3.4 Required: `multitrack.auth` Integration

```python
import os, secrets
from pathlib import Path
from multitrack.auth import make_auth_routes

self.app.secret_key = os.environ.get("MYTRACKER_SECRET_KEY", secrets.token_hex(32))
make_auth_routes(self.app, db_path=Path("Accts/pw.json.gpg"), tracker_name="My Tracker")
```

`make_auth_routes` registers `/login`, `/logout`, `/register` and installs a
`before_request` guard that redirects unauthenticated requests to `/login`.

---

### 3.5 Required: Isolated User DB

Each Tracker App stores `Accts/pw.json.gpg` within its own repo.
Add `**/Accts/*.gpg` to `.gitignore` — the DB is never committed.

The DB is created by `wsCmd.py --setup` using the tracker app's own `APP_GPG_PASSPHRASE`
(or tracker-specific equivalent). The platform derives this as `<master>_<stanza_key>`.

---

### 3.6 Recommended: Tracker ID Convention

- Short, lowercase, URL-safe slug: `admin`, `llc`, `health`
- Matches: PA directory name, mount point, env var prefix (`LLC_`, `HEALTH_`)
- `stanza_key` in `MultiTaskWS_config.json` must equal the slug

---

### 3.7 Recommended: Tracker Repo Layout

```
<tracker-repo>/
│
├── wsgi.py                 ← WSGI entry point; exposes `application`
├── wsCmd.py                ← Tracker CLI: --setup and --start
├── Accts/                  ← pw.json.gpg (gitignored)
│
├── <tracker>/              ← Tracker package
│   ├── __init__.py
│   ├── app.py              ← Flask app class
│   └── templates/          ← Jinja2 templates (use url_for throughout)
│
└── docs/
    └── design_<tracker>.md ← Tracker-specific design notes
```

`sys_path` registered in the platform config must point to the directory
containing `wsgi.py` and `wsCmd.py` (the repo root shown above).

---

## 4. PythonAnywhere Integration — Adding & Updating Tracker Apps

> **Prerequisite**: platform is already deployed (see [design_webserver.md §4](design_webserver.md)).
> Tracker App repo must satisfy the contract in §2 above.

### 4.1 Adding an External Tracker App

**Step 1 — Clone the tracker app repo on PA**

```bash
mkdir -p ~/<trackerid> && cd ~/<trackerid>
git clone <tracker-repo-url>
```

**Step 2 — Install the tracker app's dependencies**

```bash
pip3.10 install --user <tracker-specific-packages>
```

**Step 3 — Run the tracker app's own setup**

```bash
cd ~/<trackerid>/<repo>/<tracker-sys-path-root>
python3.10 wsCmd.py --setup
```

This seeds `Accts/pw.json.gpg` and writes the tracker stanza to
`~/.MultiTaskWS/MultiTaskWS_config.json`.

**Step 4 — Register the tracker app in the platform config**

Add a Tracker App entry to the `"Trackers"` list in
`~/.MultiTaskWS/MultiTaskWS_config.json`:

```json
{
  "name":        "<Tracker display name>",
  "mount":       "/<trackerid>",
  "url":         "/<trackerid>/login",
  "description": "<one-line description>",
  "status":      "online",
  "sys_path":    "/home/trackerid/<trackerid>/<repo>/<root>",
  "stanza_key":  "<trackerid>"
}
```

**Step 5 — PA Web tab → Reload**

Visit `https://paDomain.com/<trackerid>/login`.

---

#### Worked example: PropRental Tracker

- for this example <trackerid> = 'llcTracker'

```bash
# Step 1 — clone
mkdir -p ~/llcTracker && cd ~/llcTracker
git clone https://github.com/myLLC_GitID/myLLC.git

# Step 2 — dependencies
pip3.10 install --user flask pandas numpy pypdf werkzeug deepdiff

# Step 3 — tracker setup
cd ~/llcTracker/myLLC/pages/AccountingData/Notebooks
python3.10 wsCmd.py --setup

# Step 4 — add to MultiTaskWS_config.json "Trackers" list:
# {
#   "name": "PropRental Tracker", "mount": "/llcTracker", "url": "/llcTracker/login",
#   "description": "W&B Group LLC — double-entry ledger & IRS forms",
#   "status": "online",
#   "sys_path": "/home/trackerid/llcTraker/myLLC/pages/AccountingData/Notebooks",
#   "stanza_key": "llc"
# }
# (tracker's wsCmd.py --setup will have written the "llc" stanza)

# Step 5 — PA Web tab → Reload
```

After reload, visit `https://paDomain.com/llcTracker/login`.

---

### 4.2 Updating a Tracker

```bash
cd ~/<trackerid>/<repo>
git pull origin main
# PA Web tab → Reload  (no WSGI file changes needed)
```

---

## 5. Key Files Reference — Tracker Side

| File | Scope | Purpose |
|------|-------|---------|
| `<trackerid>/wsgi.py` | Tracker | WSGI entry point; exposes `application` |
| `<trackerid>/wsCmd.py` | Tracker | Tracker CLI — `--setup` (DB seed + stanza) and `--start` (standalone) |
| `<trackerid>/Accts/pw.json.gpg` | Tracker | Encrypted user DB (gitignored) |
| `<trackerid>/app.py` | Tracker | Flask app class — calls `make_auth_routes`, defines views |
| `<trackerid>/templates/` | Tracker | Jinja2 templates — must use `url_for()` throughout |

> For platform-side key files, see [design_webserver.md §5](design_webserver.md).

---

## 6. adminTracker User DB Schema

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

The `wbgadminWS` admin record stores a config pointer in `notes`:

```json
{
  "username":   "wbgadminWS",
  "password":   "",
  "full_name":  "webserver admin",
  "role":       "member",
  "notes":      "/home/trackerid/.MultiTaskWS/MultiTaskWS_config.json",
  "created_at": "..."
}
```

`multitrack.auth.ALLOWED_ROLES` default: `["member", "llcManager", "bookkeeper", "accountant"]`.

---

## 7. Role Permissions

> **Note:** Permission enforcement is a future implementation item.

Refer to each tracker for details. 
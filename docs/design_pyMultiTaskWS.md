# MultiTrack Web Platform — Architecture & Setup

> For tracker app development and PA integration of external trackers, see
> [design_trackerApp.md](design_trackerApp.md).

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
| `wsCmd.py` | **Platform** | Interactive setup: passphrase, deps, adminTracker DB seed, write `~/.MultiTaskWS/config.json` | Full WSGI dispatcher (all Trackers via DispatcherMiddleware) |
| `adminTracker/wsCmd.py` | **AdminTracker** | Reseed adminTracker user DB (reads passphrase from platform config) | AdminTracker standalone, no dispatcher prefix |
| `<tracker>/wsCmd.py` | **Tracker** | Tracker-specific setup (reads passphrase from tracker config) | Tracker standalone |

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
├── /rentalTracker  ────→  llcRentalTracker  (WBGroup LLC Editor)
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

### 1.4 Platform Config — `~/.MultiTaskWS/config.json`

`wsCmd.py --setup` writes the platform config to `~/.MultiTaskWS/config.json`.
This file holds platform credentials and one stanza per registered Tracker:

```json
{
  "WEB_GPG_PASSPHRASE": "...",
  "WEB_SECRET_KEY":     "...",
  "WebServer":          "Host_wbgroup",
  "Trackers": [ ... ],
  "adminTracker": {
    "APP_GPG_PASSPHRASE": "...",
    "APP_SECRET_KEY":     "..."
  },
  "llcRentalTracker": {
    "APP_GPG_PASSPHRASE": "...",
    "APP_SECRET_KEY":     "..."
  }
}
```

Each Tracker entry in `Trackers` is used to:
- Populate `adminTracker.registry.TRACKERS` (shown on the admin home page)
- Mount the Tracker's Flask app in the dispatcher

External Trackers (not built into this repo) carry `sys_path` and a `stanza_key`
that matches the git repo name. Their credentials live in a top-level stanza
using the same name:

```json
{
  "Trackers": [
    {
      "name":        "LLC Rental Tracker",
      "mount":       "/rentalTracker",
      "url":         "/rentalTracker/login",
      "description": "W&B Group LLC — double-entry ledger & IRS forms",
      "status":      "online",
      "sys_path":    "/home/wbgroup/pyTrackers/llcRentalTracker",
      "stanza_key":  "llcRentalTracker"
    }
  ],
  "llcRentalTracker": {
    "APP_GPG_PASSPHRASE": "...",
    "APP_SECRET_KEY":     "..."
  }
}
```

`make_application()` reads `cfg["llcRentalTracker"]`, injects those env vars, adds
`sys_path` to `sys.path`, then imports `wsgi.py` from that root.

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

The `<TrackerID>` must be globally unique across the Platform and matches the `mount`
value in the config (e.g., `admin`, `rentalTracker`, `health`).

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

Each Tracker uses its own `APP_GPG_PASSPHRASE` for its user DB. The tracker's
`wsCmd.py --setup` sets this passphrase and writes it to both
`~/.<trackerRepo>/config.json` and the platform stanza.

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
    ├── design_pyMultiTaskWS.md ← This file — platform architecture & setup
    ├── design_trackerApp.md    ← Tracker app development & PA integration
    ├── design_setup.md         ← Config & setup concepts; AS-IS → TO-BE action plan
    ├── design_setup_llcRentalTracker.md ← llcRentalTracker TO-BE setup
    └── design_setup_adminTracker.md     ← adminTracker TO-BE setup
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
and writes `~/.MultiTaskWS/config.json`.

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
> For adding external Trackers after initial platform setup, see
> [design_trackerApp.md §4](design_trackerApp.md).

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
├── pyTrackers/
│   └── llcRentalTracker/       ← llcRentalTracker repo
│       └── wsgi.py             ← LLC Tracker entry point
│
└── ~/.MultiTaskWS/
    └── config.json             ← Platform config (chmod 600, not in git)
```

---

### 4.2 Step 0 — PA Dashboard: Create the Web App

1. Sign in to [pythonanywhere.com](https://www.pythonanywhere.com).
2. **Dashboard → Web tab → Add a new web app**
   - Framework: **Manual configuration**
   - Python version: **3.10**
3. In the **Code** section:
   - **WSGI configuration file** → edit the auto-generated file (see note below)
   - **Source code** → `/home/wbgroup/pyMultiTaskWS/`

> **PA WSGI file note:** PA generates a file at
> `/var/www/wbgroup_pythonanywhere_com_wsgi.py`. Edit it to contain:
> ```python
> import sys
> from pathlib import Path
> _here = Path("/home/wbgroup/pyMultiTaskWS")
> if str(_here) not in sys.path:
>     sys.path.insert(0, str(_here))
> from wsCmd import WsCmd
> application = WsCmd().make_application()
> ```

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
| 1 | Prompts for platform passphrase → stored as `WEB_GPG_PASSPHRASE` (min 12 chars, confirmed) |
| 2 | Installs `flask` and `werkzeug` via pip |
| 3 | Generates `WEB_SECRET_KEY`; writes `~/.MultiTaskWS/config.json` with `adminTracker` stanza |
| 4 | Seeds `adminTracker/Accts/pw.json.gpg` with `webadmin / WebAdmin0!` |

---

### 4.5 Step 3 — Reload and Test

1. PA **Web tab → Reload** button.
2. Visit `https://wbgroup.pythonanywhere.com/admin/login`
   - Sign in: `webadmin / WebAdmin0!`
   - **Tracker Apps** card shows registered Trackers
   - **Runtime → Mount point** shows `/admin`

---

## 5. Key Files Reference — Platform

| File | Scope | Purpose |
|------|-------|---------|
| `wsCmd.py` | Platform | CLI — `--setup` (platform config) and `--start` (full dispatcher) |
| `wsgi.py` | Platform | PA entry point — thin wrapper around `WsCmd().make_application()` |
| `~/.MultiTaskWS/config.json` | Platform | Credentials + Tracker list (chmod 600, not in git) |
| `multitrack/auth.py` | Platform | Shared auth — import in every Tracker |
| `multitrack/templates/login.html` | Platform | Generic login page |
| `multitrack/templates/register.html` | Platform | Generic register page |
| `adminTracker/registry.py` | AdminTracker | Tracker list — populated by `make_application()`, shown on home |
| `adminTracker/wsgi.py` | AdminTracker | WSGI entry point; auto-seeds webadmin user |
| `adminTracker/app.py` | AdminTracker | `AdminTrackerApp` — Flask class, home page shows tracker list |
| `adminTracker/wsCmd.py` | AdminTracker | Tracker CLI — `--setup` (DB reseed) and `--start` (standalone) |
| `adminTracker/templates/home.html` | AdminTracker | Tracker index — lists all registered apps |

> For tracker-side key files, see [design_trackerApp.md §5](design_trackerApp.md).

---

## 6. Security Notes

| Concern | Approach |
|---------|---------|
| Credentials in config | `~/.MultiTaskWS/config.json` is `chmod 600`; never in git |
| GPG passphrase | Per-tracker `APP_GPG_PASSPHRASE` unique per tracker; passed to `gpg` via `os.pipe()` — invisible in `ps aux` |
| Flask secret key | Generated at setup; stored per-tracker stanza in platform config and in `~/.<trackerRepo>/config.json` |
| User passwords | SHA-256 hashed; plaintext never written to disk |
| Cross-Tracker isolation | Separate user DBs, separate Flask secret keys, separate passphrases |
| User DB files (adminTracker) | `**/Accts/*.gpg` excluded from git via `.gitignore` |
| User DB files (external trackers) | Live in their BUS data repo; see [design_setup.md](design_setup.md) |

# MultiTaskWS — Change Log

---

## v0.1.0 — 2026-05-16/17

**Release branch:** `release/v0.1`  
**Status:** Deployed to PythonAnywhere (`wbgroup.pythonanywhere.com`)

### Platform (`wsCmd.py`, `wsgi.py`)

- Consolidated all setup into a single top-level `wsCmd.py` with `--setup` and `--start`
- `--setup`: prompts for master passphrase, installs deps, writes `~/.MultiTaskWS/MultiTaskWS_config.json`, seeds adminTracker DB
- `--start`: runs full WSGI dispatcher via `DispatcherMiddleware`; `--wsgi` flag mirrors PA behavior (no reloader)
- `--start --port`: configurable bind port (default 8080)
- Added thin `wsgi.py` as PA entry point (`WsCmd().make_application()`)
- Removed `multitrack_wsgi.py` and `setup/` folder (superseded by `wsCmd.py`)
- Removed `setupWebServerCmd.py` (obsolete root-level leftover)

### Per-Tracker Passphrase & Stanza Design

- Each tracker has its own stanza in `MultiTaskWS_config.json` keyed by `stanza_key`
- Tracker passphrase derived as `<master>_<stanza_key>` at platform setup time
- Top-level config key: `WEB_GPG_PASSPHRASE` (master, recovery only)
- Per-tracker stanza key: `APP_GPG_PASSPHRASE` (renamed from `MULTITRACK_GPG_PASSPHRASE`)
- `multitrack/auth.py` `_GPG_PASSPHRASE_ENV` updated to `APP_GPG_PASSPHRASE`
- Each tracker reads only its own stanza — no access to master passphrase

### adminTracker (`adminTracker/`)

- Renamed from `trackerWeb` → `adminTracker` (TrackerID: `admin`, mount: `/admin`)
- Added `app.py` — `AdminTrackerApp` Flask class with home page showing registered trackers
- Added `wsgi.py` — standalone WSGI entry point; auto-seeds `webadmin` user on first import
- Added `wsCmd.py` — tracker-level CLI (`--setup`, `--start`); reads from `adminTracker` stanza only
- Added `registry.py` — module-level `TRACKERS` list populated by `make_application()` before import
- Added `templates/home.html` — dashboard with Platform Status, Tracker Apps, Session, Runtime cards
- Added **StopWeb** action: `POST /admin/stop` sends `SIGTERM`; confirmation dialog in UI
- FIXME block documents future async 2-minute shutdown notification design

### PA Deployment

- PA username updated: `frankr6591` → `wbgroup`
- PA WSGI config file points to auto-generated `/var/www/wbgroup_pythonanywhere_com_wsgi.py` (edited to import `WsCmd().make_application()`)
- Verified working: `https://wbgroup.pythonanywhere.com/admin/login`

### Documentation (`docs/`)

- Split `design_webserver.md` into two focused files:
  - `design_webserver.md` — platform architecture, local setup, PA platform deployment, security
  - `design_trackerApp.md` — tracker repo contract, developer guidelines, PA tracker integration, user DB schema, roles
- Added `design_trackerApp.md` §2 integration checklist (4 required artifacts)
- Fixed stale `MULTITRACK_GPG_PASSPHRASE` references throughout docs
- Added `--setup` prerequisite note to §3.3 Start Locally
- Rewrote §4.6 as tracker-agnostic "Adding an External Tracker" with PropRental worked example
- Added PA WSGI file edit note from live deployment experience

---

## Backlog / Known Items

- `wsCmd.py --register-tracker` command (currently manual JSON edit to add tracker to config)
- StopWeb: async 2-minute shutdown notification to each tracker (FIXME in `adminTracker/app.py`)
- Role permission enforcement (currently defined but not enforced — see `design_trackerApp.md §7`)
- PropRental Tracker (LLC-WB-Group) integration into PA — pending LLC repo restructuring

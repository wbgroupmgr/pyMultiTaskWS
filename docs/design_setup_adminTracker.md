# adminTracker — Configuration & Setup Guide

> Overall concepts and action plan: [design_setup.md](design_setup.md)
> Platform architecture: [design_pyMultiTaskWS.md](design_pyMultiTaskWS.md)

---

## 1. Overview

`adminTracker` is the built-in platform administration tracker. It is part of the
`pyMultiTaskWS` repo — not a separate git repo. It:

- Mounts at `/admin` in the dispatcher
- Displays the registered Tracker list (from `adminTracker/registry.py`)
- Manages its own `Accts/pw.json.gpg` user database
- Is set up as part of `pyMultiTaskWS/wsCmd.py --setup` (not a separate `--setup` command)

`adminTracker` has no BUS data repo. Its user DB is internal to the `pyMultiTaskWS` repo.

---

## 2. Config Files — TO-BE Schema

### 2.1 `~/.MultiTaskWS/config.json` — platform config (sole authority for adminTracker)

adminTracker's secrets are held in the platform config stanza — there is no separate
`~/.adminTracker/config.json` secrets block needed for runtime:

```json
{
  "WEB_GPG_PASSPHRASE": "<platform passphrase>",
  "WEB_SECRET_KEY":     "<platform Flask signing key>",
  "WebServer":          "Host_wbgroup",
  "Trackers": [
    {
      "name":        "adminTracker",
      "mount":       "/admin",
      "url":         "/admin/login",
      "description": "Platform Administration",
      "status":      "online",
      "stanza_key":  "adminTracker",
      "builtin":     true
    }
  ],
  "adminTracker": {
    "APP_GPG_PASSPHRASE": "<unique — not shared with any other tracker>",
    "APP_SECRET_KEY":     "<unique random hex>"
  }
}
```

`chmod 600`. **Never committed to git.**

### 2.2 `~/.adminTracker/config.json` — tracker config (convention)

adminTracker follows the same per-tracker config pattern as `llcRentalTracker`.
File is created at setup. For the built-in tracker it currently holds minimal metadata:

```json
{
  "trackerName": "adminTracker",
  "WebServer":   "<host tag>"
}
```

> **Why this file:** ensures the `~/.<trackerRepo>/config.json` pattern is consistent
> across all trackers. Future: may hold adminTracker-specific non-secret config.

`chmod 600`. **Never committed to git.**

### 2.3 `adminTracker/Accts/pw.json.gpg` — user database

GPG-symmetric, encrypted with adminTracker's `APP_GPG_PASSPHRASE`. Lives inside
the `pyMultiTaskWS` repo directory. **Gitignored** — not committed.

Unlike `llcRentalTracker`, adminTracker's user DB is local-only (not in a shared BUS repo).
Each host manages its own adminTracker users independently.

---

## 3. Platform Setup Workflow

### 3.1 `wsCmd.py --setup` — platform + adminTracker combined

```bash
cd ~/pyMultiTaskWS
python3 wsCmd.py --setup
```

What it does:

| Step | Action |
|---|---|
| 1 | Prompts: `Enter WEB_GPG_PASSPHRASE` (platform master passphrase, min 12 chars) |
| 2 | Generates `WEB_SECRET_KEY` (random) |
| 3 | Prompts: `Enter adminTracker APP_GPG_PASSPHRASE` (unique; must differ from platform passphrase) |
| 4 | Generates adminTracker `APP_SECRET_KEY` (random) |
| 5 | Writes `~/.MultiTaskWS/config.json` with platform + `adminTracker` stanza |
| 6 | Creates `~/.adminTracker/config.json` |
| 7 | Seeds `adminTracker/Accts/pw.json.gpg` with `webadmin / WebAdmin0!` |

### 3.2 Start

**Full dispatcher (PA or local):**
```bash
python3 wsCmd.py --start
# → loads all registered trackers; dispatcher at http://127.0.0.1:8080
# → visit http://127.0.0.1:8080/admin/login
```

**adminTracker standalone only (dev):**
```bash
python3 adminTracker/wsCmd.py --start
# → standalone at http://127.0.0.1:8081/login (no /admin prefix)
```

---

## 4. Fresh-Start Procedure

Run on **local first**, then repeat on **PA**. Run **after** llcRentalTracker
standalone is verified (see [design_setup_llcRentalTracker.md](design_setup_llcRentalTracker.md)).

### Step 0 — Record current adminTracker passphrase (if PA has one)

```bash
# PA console:
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.MultiTaskWS/MultiTaskWS_config.json').read_text())
at = cfg.get('adminTracker', {})
print('APP_GPG_PASSPHRASE:', at.get('APP_GPG_PASSPHRASE'))
print('WEB_GPG_PASSPHRASE:', cfg.get('WEB_GPG_PASSPHRASE'))
print('WEB_SECRET_KEY    :', cfg.get('WEB_SECRET_KEY', '')[:16], '...')
"
```

### Step 1 — Delete old config and git clone

```bash
rm ~/.MultiTaskWS/MultiTaskWS_config.json   # or: rm -f ~/.MultiTaskWS/config.json
rm -rf ~/.adminTracker/                     # if exists
rm -rf ~/pyMultiTaskWS/                     # git clone

# Do NOT delete ~/.llcRentalTracker/config.json — already migrated in Phase A
```

### Step 2 — Fresh clone

```bash
cd ~
git clone https://github.com/wbgroupmgr/pyMultiTaskWS.git
```

### Step 3 — Run platform setup

```bash
cd ~/pyMultiTaskWS
python3 wsCmd.py --setup
# Prompts: WEB_GPG_PASSPHRASE, adminTracker APP_GPG_PASSPHRASE
# Creates ~/.MultiTaskWS/config.json, ~/.adminTracker/config.json
# Seeds adminTracker/Accts/pw.json.gpg
```

> **Note on passphrase choice:**
> `WEB_GPG_PASSPHRASE` — new random value is fine (no shared file to decrypt).
> `APP_GPG_PASSPHRASE` (adminTracker) — new random value is fine (fresh user DB;
> old adminTracker users are not preserved across fresh starts).

### Step 4 — Register llcRentalTracker with platform

At this point `~/.llcRentalTracker/config.json` already has `APP_GPG_PASSPHRASE`
and `APP_SECRET_KEY` from Phase A. Register it with the platform:

```bash
cd ~/pyTrackers/llcRentalTracker
python3 wsCmd.py --setup --llcName WBGroupLLC
# With Phase 2 code: reads ~/.llcRentalTracker/config.json secrets:
# Writes llcRentalTracker stanza to ~/.MultiTaskWS/config.json
# (does NOT re-prompt for passphrase — already in tracker config)
```

**Manually verify the platform config now has both stanzas:**

```bash
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.MultiTaskWS/config.json').read_text())
for key in ('adminTracker', 'llcRentalTracker'):
    s = cfg.get(key, {})
    print(f'{key}: GPG={'SET' if s.get('APP_GPG_PASSPHRASE') else 'MISSING'}, KEY={'SET' if s.get('APP_SECRET_KEY') else 'MISSING'}')
print('Trackers:', [t.get('name') for t in cfg.get('Trackers', [])])
"
```

### Step 5 — PA WSGI file (PA only — one-time)

PA WSGI file `/var/www/wbgroup_pythonanywhere_com_wsgi.py` must point to platform:

```python
import sys
from pathlib import Path
_here = Path("/home/wbgroup/pyMultiTaskWS")
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from wsCmd import WsCmd
application = WsCmd().make_application()
```

This file is set once on PA manually. It does not change on redeployment.

### Step 6 — Reload and test

```bash
# PA Web tab → Reload
# Visit https://wbgroup.pythonanywhere.com/admin/login
# Login: webadmin / WebAdmin0!  → change password immediately
```

---

## 5. Verification Checklist

```bash
# 1. Platform config present and complete
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.MultiTaskWS/config.json').read_text())
print('WEB_GPG_PASSPHRASE:', 'SET' if cfg.get('WEB_GPG_PASSPHRASE') else 'MISSING')
print('WEB_SECRET_KEY    :', 'SET' if cfg.get('WEB_SECRET_KEY') else 'MISSING')
for key in ('adminTracker', 'llcRentalTracker'):
    s = cfg.get(key, {})
    pp = 'SET' if s.get('APP_GPG_PASSPHRASE') else 'MISSING'
    sk = 'SET' if s.get('APP_SECRET_KEY') else 'MISSING'
    print(f'{key}: GPG={pp} KEY={sk}')
print('Trackers:', [t.get('stanza_key') for t in cfg.get('Trackers', [])])
"

# 2. adminTracker config present
ls -la ~/.adminTracker/config.json    # should exist, chmod 600

# 3. adminTracker user DB decrypts
AT_PP=$(python3 -c "
import json; from pathlib import Path
print(json.loads((Path.home()/'.MultiTaskWS/config.json').read_text())['adminTracker']['APP_GPG_PASSPHRASE'])
")
gpg --batch --decrypt --passphrase "$AT_PP" \
    ~/pyMultiTaskWS/adminTracker/Accts/pw.json.gpg 2>/dev/null \
  && echo "adminTracker pw.json.gpg ✓" || echo "DECRYPT FAILED"

# 4. Full dispatcher starts
cd ~/pyMultiTaskWS
python3 wsCmd.py --start &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/admin/login
# Expected: 200
kill %1

# 5. llcRentalTracker mounted (PA hosted mode)
# Visit https://<pa-domain>/rentalTracker/login  → should reach login page
# Visit https://<pa-domain>/admin/login          → adminTracker home, lists llcRentalTracker
```

---

## 6. Roles and Seed Users

| User | Password | Role | Notes |
|---|---|---|---|
| `webadmin` | `WebAdmin0!` | `member` | Default seed — change immediately |

`adminTracker/Accts/pw.json.gpg` schema (standard record):

```json
{
  "username":   "webadmin",
  "password":   "<sha256-hex>",
  "full_name":  "Web Admin",
  "role":       "member",
  "created_at": "..."
}
```

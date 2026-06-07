# llcRentalTracker — Configuration & Setup Guide

> Overall concepts and action plan: [design_configuration.md](design_configuration.md)
> Platform architecture: [design_pyMultiTaskWS.md](design_pyMultiTaskWS.md)

---

## 1. Overview

`llcRentalTracker` is the LLC accounting tracker app. It can run:

- **Standalone** — `python3 wsCmd.py --start` on local or PA, no pyMultiTaskWS needed
- **Hosted** — mounted at `/rentalTracker` by the pyMultiTaskWS dispatcher on PA

It involves two repos:

| Repo | Path (PA) | Path (local) |
|---|---|---|
| `llcRentalTracker` (app code) | `~/pyTrackers/llcRentalTracker/` | `~/GDrive/dev/pyTrackers/llcRentalTracker/` |
| `LLC-WBGroup` (BUS data) | `~/llc/LLC-WBGroup/` | `~/GDrive/Family/Assets/LLC-WBGroup/` |

---

## 2. Config Files — TO-BE Schema

### 2.1 `~/.llcRentalTracker/config.json` — sole runtime authority

`APP_SECRET_KEY` is **per-tracker** (one Flask signing key for the whole app).
`APP_GPG_PASSPHRASE` is **per-BUS** — each BUS encrypts its own `pw.json.gpg` independently.

```json
{
  "default": ["WBGroupLLC", 2025],
  "APP_SECRET_KEY": "<one Flask signing key for this llcRentalTracker instance>",
  "llcList": [
    {
      "llcName":            "WBGroupLLC",
      "dataName":           "WBGroupLLC",
      "bus_repo":           "<absolute path to LLC-WBGroup>",
      "books_dir":          "books",
      "years":              [2025, 2026],
      "APP_GPG_PASSPHRASE": "<unique passphrase — sole key for WBGroupLLC pw.json.gpg>"
    },
    {
      "llcName":            "<otherBUS>",
      "dataName":           "<otherBUS>",
      "bus_repo":           "<absolute path to otherBUS repo>",
      "books_dir":          "books",
      "years":              [2025],
      "APP_GPG_PASSPHRASE": "<unique passphrase — different from WBGroupLLC>"
    }
  ]
}
```

`chmod 600`. **Never in any repo.**

`APP_GPG_PASSPHRASE` is the sole encryption key for that BUS's `pw.json.gpg`.
**Same value must be used on every host** (PA, local) for the same BUS.
Different BUS repos use different passphrases — a compromised BUS key exposes nothing else.

### 2.2 `LLC-WBGroup/books/Accts/pw.json.gpg` — user database

GPG-symmetric, encrypted with `APP_GPG_PASSPHRASE`. Lives in the BUS data repo.
**Only PA (master host) commits and pushes this file.** All other hosts pull only.

### 2.3 `LLC-WBGroup/books/Accts/llcProfile_WBGroupLLC.json` — entity data only

```json
{
  "entity": { ... },
  "F1065":  { ... }
}
```

No filesystem paths, no passphrase, no year fields. These are migration artifacts —
remove them if present.

### 2.4 `~/.MultiTaskWS/config.json` — platform routing entry (hosted mode only)

When running under `pyMultiTaskWS`, the tracker is registered in the platform `Trackers`
list for dispatcher routing. `wsCmd.py --setup` writes this entry when
`~/.MultiTaskWS/config.json` is present. **No secrets are stored here** — the tracker
reads secrets exclusively from `~/.llcRentalTracker/config.json`.

```json
{
  "name":       "LLC Rental Tracker",
  "stanza_key": "llcRentalTracker",
  "gitRemote":  "wbgroupmgr/llcRentalTracker",
  "mount":      "/rentalTracker",
  "url":        "/rentalTracker/login",
  "description":"Financial Mgmt App for Property Rental LLC",
  "status":     "online",
  "builtin":    false,
  "sys_path":   "<absolute path to llcRentalTracker clone>"
}
```

---

## 3. Setup Workflow

### 3.1 `--newBus` — Register a BUS repo

```bash
cd <llcRentalTracker root>
python3 wsCmd.py --newBus <path/to/LLC-WBGroup> --year 2025 --llcName WBGroupLLC
```

What it does:
- Prompts: `Enter APP_GPG_PASSPHRASE for WBGroupLLC` (unique per BUS — must match the passphrase that encrypted that BUS's `pw.json.gpg`)
- Creates `~/.llcRentalTracker/config.json` (if absent)
- Adds `{ llcName, bus_repo, years, APP_GPG_PASSPHRASE }` to `llcList`
- Sets `default` to `WBGroupLLC/2025`

To add a second year to an existing BUS:

```bash
python3 wsCmd.py --newBus <path/to/LLC-WBGroup> --year 2026 --llcName WBGroupLLC
# appends 2026 to years: list; APP_GPG_PASSPHRASE already in stanza; no re-prompt
```

To add a second BUS:

```bash
python3 wsCmd.py --newBus <path/to/otherBUS> --year 2025 --llcName otherBUS
# prompts for otherBUS APP_GPG_PASSPHRASE (different from WBGroupLLC)
# adds new stanza to llcList; default remains WBGroupLLC
```

### 3.2 `--setup` — Finalize secrets + create user DB

```bash
python3 wsCmd.py --setup --llcName WBGroupLLC
```

What it does (for `--llcName WBGroupLLC`):
1. Reads `WBGroupLLC.APP_GPG_PASSPHRASE` from `llcList` stanza (set by `--newBus`)
2. Generates `APP_SECRET_KEY` (random 64-char hex); writes to top-level config
3. Creates `LLC-WBGroup/books/Accts/pw.json.gpg` encrypted with `WBGroupLLC.APP_GPG_PASSPHRASE`
4. If `~/.MultiTaskWS/config.json` exists: writes routing entry to `Trackers` list (no secrets)
5. Prints: `Push pw.json.gpg to BUS repo (PA = master host)`

> **Note:** `APP_SECRET_KEY` is generated once for the tracker, not per BUS. If you run
> `--setup` for a second BUS (`--llcName otherBUS`), the existing `APP_SECRET_KEY` is
> reused — only `pw.json.gpg` is created for the new BUS using its own passphrase.
>
> On local dev, step 4 is skipped silently (no `~/.MultiTaskWS/config.json`) — correct
> behavior for standalone mode.

### 3.3 `--start` — Start the app

```bash
python3 wsCmd.py --start --llcName WBGroupLLC --year 2025 [--port 5000] [--load]
```

Startup injection (sole source — no fallback):
```
~/.llcRentalTracker/config.json:
  APP_SECRET_KEY              (top-level)      → os.environ["LLC_SECRET_KEY"]
  llcList[WBGroupLLC].APP_GPG_PASSPHRASE       → os.environ["LLC_GPG_PASSPHRASE"]
```

Hard fail if either key is absent — run `--setup` first.

---

## 4. Fresh-Start Procedure

Run on **local first**, then repeat on **PA**. Identical steps; only paths differ.

### Step 0 — Record current secrets (before deleting anything)

```bash
# Read the current LLC_GPG_PASSPHRASE from the existing profile (current code, PA)
python3 -c "
import json; from pathlib import Path
p = Path('~/llc/LLC-WBGroup/books/Accts/llcProfile_WBGroupLLC.json').expanduser()
cfg = json.loads(p.read_text())
mw = cfg.get('MultiTaskWS_Config', {})
print('LLC_GPG_PASSPHRASE:', mw.get('LLC_GPG_PASSPHRASE'))
print('LLC_SECRET_KEY    :', mw.get('LLC_SECRET_KEY'))
"
```

Record these values. The `LLC_GPG_PASSPHRASE` value becomes your `APP_GPG_PASSPHRASE`
in the new setup — using the same value means `pw.json.gpg` continues to decrypt
without requiring user re-registration.

### Step 1 — Delete old config and git clones

```bash
# Delete tracker config (contains stale LLC_ keys and master_passphrase)
rm ~/.llcRentalTracker/config.json

# Delete git clones
rm -rf <path/to/llcRentalTracker>
rm -rf <path/to/LLC-WBGroup>
```

### Step 2 — Fresh clone both repos

```bash
# App code
git clone https://github.com/wbgroupmgr/llcRentalTracker.git <path/to/llcRentalTracker>

# BUS data
git clone https://github.com/wbgroupmgr/LLC-WBGroup.git <path/to/LLC-WBGroup>
```

### Step 3 — Register BUS + set passphrase

```bash
cd <path/to/llcRentalTracker>
python3 wsCmd.py --newBus <path/to/LLC-WBGroup> --year 2025 --llcName WBGroupLLC
# Prompt: Enter APP_GPG_PASSPHRASE → enter the value recorded in Step 0
```

### Step 4 — Add 2026 year

```bash
python3 wsCmd.py --newBus <path/to/LLC-WBGroup> --year 2026 --llcName WBGroupLLC
# No prompt — passphrase already stored
```

### Step 5 — Run setup

```bash
python3 wsCmd.py --setup --llcName WBGroupLLC
# Generates APP_SECRET_KEY; writes to config
# Creates pw.json.gpg if absent, OR verifies existing pw.json.gpg decrypts correctly
```

> If you used the same `APP_GPG_PASSPHRASE` as the old `LLC_GPG_PASSPHRASE`, the
> existing `pw.json.gpg` pulled from the BUS repo in Step 2 continues to work.
> No need to push a new `pw.json.gpg`.

### Step 6 — Clean llcProfile (PA only — master host pushes)

```bash
cd <path/to/LLC-WBGroup>
python3 -c "
import json; from pathlib import Path
p = Path('books/Accts/llcProfile_WBGroupLLC.json')
cfg = json.loads(p.read_text())
clean = {k: cfg[k] for k in ('entity', 'F1065') if k in cfg}
p.write_text(json.dumps(clean, indent=2))
print('Removed:', [k for k in cfg if k not in clean])
"
git add books/Accts/llcProfile_WBGroupLLC.json
git commit -m "refactor(profile): entity/F1065 only"
git push
```

### Step 7 — Start and test

```bash
cd <path/to/llcRentalTracker>
python3 wsCmd.py --start --llcName WBGroupLLC --year 2025 --port 5000 --load
# Visit http://localhost:5000/rentalTracker/login
# Login: llcgroupmgr / llcManager0!  (or existing password if pw.json.gpg reused)
```

### Step 8 — Verification

```bash
# 1. Config is clean
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.llcRentalTracker/config.json').read_text())
s = cfg.get('secrets', {})
print('APP_GPG_PP    :', 'SET' if s.get('APP_GPG_PASSPHRASE') else 'MISSING')
print('APP_SECRET_KEY:', 'SET' if s.get('APP_SECRET_KEY') else 'MISSING')
print('LLC_ stale    :', 'STALE — REMOVE' if s.get('LLC_GPG_PASSPHRASE') else 'absent ✓')
print('master_pp     :', 'PRESENT — REMOVE' if 'master_passphrase' in cfg else 'absent ✓')
stanza = cfg['llcList'][0]
print('llcName       :', stanza.get('llcName'))      # WBGroupLLC
print('years         :', stanza.get('years'))        # [2025, 2026]
"

# 2. pw.json.gpg decrypts
APP_PP=$(python3 -c "
import json; from pathlib import Path
print(json.loads((Path.home()/'.llcRentalTracker/config.json').read_text())['secrets']['APP_GPG_PASSPHRASE'])
")
gpg --batch --decrypt --passphrase "$APP_PP" \
    <path/to/LLC-WBGroup>/books/Accts/pw.json.gpg 2>/dev/null \
  && echo "pw.json.gpg decrypts ✓" || echo "DECRYPT FAILED"

# 3. Run test suite
cd <path/to/llcRentalTracker>/pages/AccountingData/Notebooks
python3 -m tests.test_stmtBS
python3 -m tests.test_stmtIS
python3 -m tests.test_stmtGL
```

---

## 5. Code Changes Required (Phase 2 + 3)

All changes are in `llcRentalTracker`. These enable the TO-BE setup flow above.

### 5.1 `wsCmd.py`

| Function | Change |
|---|---|
| `TRACKER_DICT` | `stanza_key` `"rentalTracker"` → `"llcRentalTracker"`; update `description` field; mount `/rentalTracker` stays |
| `provision_new_bus()` | Remove `_ensure_master_passphrase()` + `_ensure_keys()`; prompt for `APP_GPG_PASSPHRASE` per BUS; write to `llcList[i].APP_GPG_PASSPHRASE` in stanza |
| `_write_secrets_to_config()` | Generate + write `APP_SECRET_KEY` at top level (once per tracker); rename `LLC_` → `APP_` keys |
| `setup()` | Remove `keys_file` / `_ensure_keys()` block; read active BUS `APP_GPG_PASSPHRASE` from `_sp.SECRETS`; generate `APP_SECRET_KEY` if absent at top level |
| `addTracker()` | Write routing-only entry to platform `Trackers` list; no secrets stanza for external tracker |
| `_inject_env_from_profile()` | Remove `MultiTaskWS_Config` fallback; read `APP_SECRET_KEY` from top-level, `APP_GPG_PASSPHRASE` from active BUS stanza; `sys.exit()` with clear message if missing |

### 5.2 `wsgi.py` — replace `_inject_secrets()`

Remove entire multi-tier function body. Replace with single-source reads:
- `APP_SECRET_KEY` from top-level config (per-tracker)
- `APP_GPG_PASSPHRASE` from the default BUS's `llcList` stanza (per-BUS)

```python
def _inject_secrets() -> None:
    # SOLE SOURCE: ~/.llcRentalTracker/config.json
    # APP_SECRET_KEY (top-level)        → LLC_SECRET_KEY env var
    # llcList[default].APP_GPG_PASSPHRASE → LLC_GPG_PASSPHRASE env var
    cfg = _sp.read_config()
    _sk = cfg.get("APP_SECRET_KEY", "")
    # _sp.SECRETS holds the active BUS stanza (populated by load_config)
    _pp = _sp.SECRETS.get("APP_GPG_PASSPHRASE", "")
    if not _pp or not _sk:
        raise RuntimeError(
            f"[wsgi] FATAL: APP_SECRET_KEY/APP_GPG_PASSPHRASE missing "
            f"from {_sp.CONFIG_FILE}.\n"
            "  Run: python3 wsCmd.py --setup --llcName <name>"
        )
    os.environ.setdefault("LLC_GPG_PASSPHRASE", _pp)
    os.environ.setdefault("LLC_SECRET_KEY", _sk)
```

### 5.3 `ledger/setup_paths.py`

- `SECRETS` global — populated from active BUS stanza (`llcList[i]`); holds `APP_GPG_PASSPHRASE`
- `APP_SECRET_KEY` lives at top-level config, not in `SECRETS`; add `SECRET_KEY` module global or read directly from `read_config()`
- Update `find_stanza()` to support nested `years:` schema (llcRentalTracker #19)
- Remove `write_secrets()` call sites that write to `llcProfile_*.json`
- `write_secrets()` now writes `APP_GPG_PASSPHRASE` into `llcList[i]` stanza; `APP_SECRET_KEY` written at top level separately

---

## 6. PA-Specific Notes

### PA = master host for BUS data

Only PA pushes commits to `LLC-WBGroup`. Local machines and other hosts pull only.
This ensures `pw.json.gpg` in the repo is always encrypted with PA's passphrase.

### After PA fresh-start, integrate with pyMultiTaskWS

Once llcRentalTracker standalone is verified on PA:

```bash
cd ~/pyMultiTaskWS
python3 wsCmd.py --setup   # adds llcRentalTracker stanza to ~/.MultiTaskWS/config.json
# OR: wsCmd.py llcRentalTracker setup already wrote the stanza if MultiTaskWS was present
```

Then reload PA web app and verify `https://<pa-domain>/rentalTracker/login`.

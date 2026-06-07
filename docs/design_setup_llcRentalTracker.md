# llcRentalTracker — Configuration & Setup Guide

> Overall concepts and action plan: [design_setup.md](design_setup.md)
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

```json
{
  "default": ["WBGroupLLC", 2025],
  "llcList": [
    {
      "llcName":   "WBGroupLLC",
      "dataName":  "WBGroupLLC",
      "bus_repo":  "<absolute path to LLC-WBGroup>",
      "books_dir": "books",
      "years":     [2025, 2026]
    }
  ],
  "secrets": {
    "APP_GPG_PASSPHRASE": "<unique passphrase for this tracker>",
    "APP_SECRET_KEY":     "<unique random hex key>"
  }
}
```

`chmod 600`. **Never in any repo.**

`APP_GPG_PASSPHRASE` is the sole encryption key for `LLC-WBGroup/books/Accts/pw.json.gpg`.
**Same value must be used on every host** — PA, local, any other host. It is the
shared key for the BUS user database.

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

### 2.4 `~/.MultiTaskWS/config.json` — platform mirror (hosted mode only)

When running under `pyMultiTaskWS`, the platform config holds a copy of the tracker's
secrets for dispatcher injection. Written by `wsCmd.py --setup` when
`~/.MultiTaskWS/config.json` is present:

```json
"llcRentalTracker": {
  "APP_GPG_PASSPHRASE": "<same value as ~/.llcRentalTracker/config.json>",
  "APP_SECRET_KEY":     "<same value>"
}
```

The stanza key is `llcRentalTracker` — matching the git repo name.

---

## 3. Setup Workflow

### 3.1 `--newBus` — Register a BUS repo

```bash
cd <llcRentalTracker root>
python3 wsCmd.py --newBus <path/to/LLC-WBGroup> --year 2025 --llcName WBGroupLLC
```

What it does:
- Prompts: `Enter APP_GPG_PASSPHRASE` (unique passphrase for this tracker)
- Creates `~/.llcRentalTracker/config.json` (if absent) with `secrets: { APP_GPG_PASSPHRASE }`
- Registers the BUS stanza in `llcList`
- Sets `default` to `WBGroupLLC/2025`

To add a second year to an existing BUS:

```bash
python3 wsCmd.py --newBus <path/to/LLC-WBGroup> --year 2026 --llcName WBGroupLLC
# appends 2026 to years: list; passphrase already stored; no re-prompt
```

### 3.2 `--setup` — Finalize secrets + create user DB

```bash
python3 wsCmd.py --setup --llcName WBGroupLLC
```

What it does:
1. Reads `APP_GPG_PASSPHRASE` from `~/.llcRentalTracker/config.json secrets:` (set by `--newBus`)
2. Generates `APP_SECRET_KEY` (random 64-char hex)
3. Writes complete `secrets: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }` to config
4. If `~/.MultiTaskWS/config.json` exists: writes `llcRentalTracker:` stanza to platform config
5. Creates `LLC-WBGroup/books/Accts/pw.json.gpg` encrypted with `APP_GPG_PASSPHRASE`
6. Prints: `Push pw.json.gpg to BUS repo (PA = master host)`

> **Note:** On local dev, `~/.MultiTaskWS/config.json` typically does not exist.
> Step 4 is skipped silently — correct behavior for standalone mode.

### 3.3 `--start` — Start the app

```bash
python3 wsCmd.py --start --llcName WBGroupLLC --year 2025 [--port 5000] [--load]
```

Startup injection (sole source — no fallback):
```
~/.llcRentalTracker/config.json secrets:
  APP_GPG_PASSPHRASE → os.environ["LLC_GPG_PASSPHRASE"]
  APP_SECRET_KEY     → os.environ["LLC_SECRET_KEY"]
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
| `TRACKER_DICT` | `stanza_key` `"rentalTracker"` → `"llcRentalTracker"`; update `description` field |
| `provision_new_bus()` | Remove `_ensure_master_passphrase()` + `_ensure_keys()`; prompt for `APP_GPG_PASSPHRASE` directly; write to `secrets:` via `_sp.write_secrets()` |
| `_write_secrets_to_config()` | Rename dict keys `LLC_SECRET_KEY` → `APP_SECRET_KEY`, `LLC_GPG_PASSPHRASE` → `APP_GPG_PASSPHRASE` |
| `setup()` | Remove `keys_file` / `_ensure_keys()` block; read `APP_GPG_PASSPHRASE` from `_sp.SECRETS`; call `_write_secrets_to_config()` to add `APP_SECRET_KEY` |
| `addTracker()` | Use `stanza_key` (`"llcRentalTracker"`) to write secrets stanza to `~/.MultiTaskWS/config.json`; source values from `_sp.SECRETS` `APP_` keys |
| `_inject_env_from_profile()` | Remove `MultiTaskWS_Config` fallback; read `APP_GPG_PASSPHRASE`/`APP_SECRET_KEY` only; `sys.exit()` with clear message if missing |

### 5.2 `wsgi.py` — replace `_inject_secrets()`

Remove entire multi-tier function body. Replace with:

```python
def _inject_secrets() -> None:
    # SOLE SOURCE: ~/.llcRentalTracker/config.json secrets:
    # APP_GPG_PASSPHRASE → LLC_GPG_PASSPHRASE  (tracker's internal env var name)
    # APP_SECRET_KEY     → LLC_SECRET_KEY
    _s  = _sp.SECRETS
    _pp = _s.get("APP_GPG_PASSPHRASE", "")
    _sk = _s.get("APP_SECRET_KEY", "")
    if not _pp or not _sk:
        raise RuntimeError(
            f"[wsgi] FATAL: APP_GPG_PASSPHRASE/APP_SECRET_KEY missing "
            f"from {_sp.CONFIG_FILE} secrets:\n"
            "  Run: python3 wsCmd.py --setup --llcName <name>"
        )
    os.environ.setdefault("LLC_GPG_PASSPHRASE", _pp)
    os.environ.setdefault("LLC_SECRET_KEY", _sk)
```

### 5.3 `ledger/setup_paths.py`

- Keep `SECRETS` global and `write_secrets()` — consumers use `APP_` key names
- Update `find_stanza()` to support nested `years:` schema (llcRentalTracker #19)
- Remove `write_secrets()` call sites that write to `llcProfile_*.json`

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

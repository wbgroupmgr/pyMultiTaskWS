# Tracker Configuration & Setup — Architecture Guide

> This document covers configuration concepts, the AS-IS → TO-BE action plan, and
> migration ordering for all three repos.
>
> Tracker-specific setup procedures:
> - [design_setup_llcRentalTracker.md](design_setup_llcRentalTracker.md)
> - [design_setup_adminTracker.md](design_setup_adminTracker.md)

---

## 1. Three-Repo Architecture

Every deployment involves three independent repositories:

| Repo | Purpose | Git remote |
|---|---|---|
| `pyMultiTaskWS` | Web platform — dispatcher, adminTracker, platform `wsCmd.py` | `wbgroupmgr/pyMultiTaskWS` |
| `llcRentalTracker` | LLC accounting tracker app — can run standalone or hosted | `wbgroupmgr/llcRentalTracker` |
| `LLC-WBGroup` | Business data — accounting JSON DBs, `pw.json.gpg` user DB | `wbgroupmgr/LLC-WBGroup` |

The repos are independent by design. `llcRentalTracker` can run without `pyMultiTaskWS`.
`LLC-WBGroup` is owned exclusively by the PA master host (no local writes).

---

## 2. Design Principles

- **Consistent and elegant above all** — `adminTracker` and `llcRentalTracker` follow the same config and setup pattern
- **Per-tracker config ownership** — each tracker owns its secrets in `~/.<trackerRepo>/config.json`; the platform config holds a mirror copy of those secrets for dispatcher injection
- **No cross-tracker shared secrets** — every tracker has its own unique `APP_GPG_PASSPHRASE` and `APP_SECRET_KEY`; a compromised tracker exposes nothing else
- **No fallback for required artifacts** — if `~/.<trackerRepo>/config.json secrets:` is missing `APP_GPG_PASSPHRASE` or `APP_SECRET_KEY`, the app fails immediately with a clear error; no silent substitution
- **PA = master host for BUS data** — only PythonAnywhere pushes commits to `LLC-WBGroup`; all other hosts pull only
- **No tracker references outside its own scope** — `llcRentalTracker` reads its own `~/.llcRentalTracker/config.json`; it does not read another tracker's config or the platform config at runtime

---

## 3. Config File Hierarchy

### 3.1 Platform Config — `~/.MultiTaskWS/config.json`

Owned by `pyMultiTaskWS`. Holds platform-level secrets and one stanza per registered tracker.
Written by `pyMultiTaskWS/wsCmd.py --setup` (platform) and by each tracker's `wsCmd.py --setup`.

```json
{
  "WEB_GPG_PASSPHRASE": "<platform passphrase>",
  "WEB_SECRET_KEY":     "<platform Flask key>",
  "WebServer":          "Host_wbgroup",
  "Trackers": [
    { "name": "adminTracker",      "mount": "/admin",         "stanza_key": "adminTracker",      ... },
    { "name": "LLC Rental Tracker","mount": "/rentalTracker", "stanza_key": "llcRentalTracker",  ... }
  ],
  "adminTracker": {
    "APP_GPG_PASSPHRASE": "<unique — not shared>",
    "APP_SECRET_KEY":     "<unique random>"
  },
  "llcRentalTracker": {
    "APP_GPG_PASSPHRASE": "<unique — not shared>",
    "APP_SECRET_KEY":     "<unique random>"
  }
}
```

`chmod 600` — owner only. **Never committed to git.**

### 3.2 Tracker Config — `~/.<trackerRepo>/config.json`

Each tracker owns its own config. For `llcRentalTracker`:

```
~/.llcRentalTracker/config.json
```

For `adminTracker` (built-in, within `pyMultiTaskWS`):

```
~/.adminTracker/config.json
```

`llcRentalTracker` schema:

```json
{
  "default": ["WBGroupLLC", 2025],
  "llcList": [
    {
      "llcName":   "WBGroupLLC",
      "dataName":  "WBGroupLLC",
      "bus_repo":  "/home/wbgroup/llc/LLC-WBGroup",
      "books_dir": "books",
      "years":     [2025, 2026]
    }
  ],
  "secrets": {
    "APP_GPG_PASSPHRASE": "<unique passphrase — sole authority>",
    "APP_SECRET_KEY":     "<unique random key>"
  }
}
```

`chmod 600`. **Never committed to git.**

### 3.3 Per-Tracker Passphrase and SECRET_KEY

| Passphrase | Config key | Config file | Env var injected |
|---|---|---|---|
| Platform GPG | `WEB_GPG_PASSPHRASE` | `~/.MultiTaskWS/config.json` | `WEB_GPG_PASSPHRASE` |
| Platform Flask key | `WEB_SECRET_KEY` | `~/.MultiTaskWS/config.json` | `WEB_SECRET_KEY` |
| adminTracker GPG | `APP_GPG_PASSPHRASE` | `~/.MultiTaskWS/config.json` `adminTracker:` | `APP_GPG_PASSPHRASE` |
| adminTracker Flask key | `APP_SECRET_KEY` | `~/.MultiTaskWS/config.json` `adminTracker:` | `APP_SECRET_KEY` |
| llcRentalTracker GPG | `APP_GPG_PASSPHRASE` | `~/.llcRentalTracker/config.json` `secrets:` | `LLC_GPG_PASSPHRASE` |
| llcRentalTracker Flask key | `APP_SECRET_KEY` | `~/.llcRentalTracker/config.json` `secrets:` | `LLC_SECRET_KEY` |

**Runtime injection rule:** Each tracker's startup reads ONLY its own
`~/.<trackerRepo>/config.json secrets:`. No fallback to the platform config.
Missing `APP_GPG_PASSPHRASE` or `APP_SECRET_KEY` → immediate hard failure.

---

## 4. Target Architecture (TO-BE)

```
~/.MultiTaskWS/config.json          (platform — never in git)
  WEB_GPG_PASSPHRASE
  WEB_SECRET_KEY
  Trackers: [ adminTracker, llcRentalTracker, ... ]
  adminTracker:      { APP_GPG_PASSPHRASE, APP_SECRET_KEY }
  llcRentalTracker:  { APP_GPG_PASSPHRASE, APP_SECRET_KEY }

~/.adminTracker/config.json         (adminTracker — never in git)
  (minimal; no BUS repo reference needed for built-in tracker)

~/.llcRentalTracker/config.json     (llcRentalTracker — never in git)
  default, llcList (M BUS × N years)
  secrets: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }   ← SOLE runtime source

LLC-WBGroup repo (BUS data):
  books/Accts/*.json                accounting data
  books/Accts/pw.json.gpg           BUS-specific user DB — PA=master-push only
  (keys.json.gpg REMOVED)
```

**What is removed in the TO-BE state:**
- `keys.json.gpg` from BUS repo (replaced by platform stanza)
- `master_passphrase` from `~/.llcRentalTracker/config.json`
- `MultiTaskWS_Config` block from `llcProfile_WBGroupLLC.json`
- Stale `LLC_GPG_PASSPHRASE`/`LLC_SECRET_KEY` keys in `secrets:` block (renamed to `APP_`)

---

## 5. Migration Ordering — AS-IS → TO-BE

### 5.1 Principle: Independent Components, Independent Migration

`llcRentalTracker` and `pyMultiTaskWS` are independent. Migrating them separately,
and testing each in isolation, reduces risk and makes rollback straightforward.

**Correct order:**

```
Phase A — llcRentalTracker (standalone validation first)
  1. Apply Phase 2+3 code changes to llcRentalTracker
  2. Fresh-start llcRentalTracker on local
  3. Validate: standalone start works, login works, accounting data loads
  4. Fresh-start llcRentalTracker on PA (standalone mode, before platform integration)
  5. Validate PA standalone

Phase B — pyMultiTaskWS (integrate after llcRentalTracker is stable)
  6. Apply any pyMultiTaskWS changes
  7. Fresh-start pyMultiTaskWS on local
  8. Validate: adminTracker works; llcRentalTracker appears in tracker list
  9. Fresh-start pyMultiTaskWS on PA
  10. Final integration test: both trackers accessible via dispatcher
```

**Why this order:**
- Validates each component independently before combining
- A regression in llcRentalTracker is visible immediately (standalone mode) without PA noise
- adminTracker is simpler; fewer moving parts; natural second step
- "Clean slate" per component means no config pollution from the old design

### 5.2 Why Local Before PA

1. Local runs faster iteration — no PA web reload cycle
2. Local mistakes don't break the live PA app
3. Once local is verified, PA is a near-identical repeat with different paths
4. The MASTER passphrase and `LLC_GPG_PASSPHRASE` are already known from the current PA state — use those values on local first to confirm they work

### 5.3 Clean-Slate vs. In-Place Migration

**Clean-slate is recommended** for this migration. In-place migration risks leaving
stale config keys that confuse the new code. The clean-slate procedure:

1. Record current secrets (before deleting anything — see §6.1)
2. Delete the old config file and git clone
3. Fresh clone + fresh `--newBus` / `--setup`
4. Use the same `APP_GPG_PASSPHRASE` value as before (so the existing `pw.json.gpg` decrypts)

> **Critical:** If you use the SAME `APP_GPG_PASSPHRASE` in the fresh setup as the
> current `LLC_GPG_PASSPHRASE`, the existing `pw.json.gpg` in the BUS repo continues
> to work — no user re-registration needed.

---

## 6. Phased Action Plan

### Phase 1 — Already done (llcRentalTracker@a47da23)
- Startup crash fix: `SECRETS = {}` guard

### Phase 2 — Config & Contract Alignment (`llcRentalTracker`)

| Item | Change | File |
|---|---|---|
| 2a | Rename platform config path `MultiTaskWS_config.json` → `config.json` | `pyMultiTaskWS` codebase |
| 2b | `TRACKER_DICT.stanza_key` `"rentalTracker"` → `"llcRentalTracker"` | `wsCmd.py` |
| 2b | `provision_new_bus()`: prompt `APP_GPG_PASSPHRASE`; remove keys.json.gpg logic | `wsCmd.py` |
| 2b | `_write_secrets_to_config()`: rename `LLC_` → `APP_` keys | `wsCmd.py` |
| 2b | `setup()`: remove `_ensure_keys()` block; read `APP_GPG_PASSPHRASE` from `_sp.SECRETS` | `wsCmd.py` |
| 2b | `addTracker()`: write `llcRentalTracker` stanza with `APP_` values to platform config | `wsCmd.py` |
| 2c | Remove `keys.json.gpg` from BUS repo; remove `master_passphrase` | `LLC-WBGroup` + `wsCmd.py` |
| 2d | Fix duplicate stanza; fix `llcName: "LLC-WBGroup"` → `"WBGroupLLC"`; nested `years:` schema | `setup_paths.py` |
| 2e | Add per-BUS deployment clause to `design_trackerApp.md §3.5` | `pyMultiTaskWS` docs |
| 2f | Create `~/.adminTracker/config.json` convention | `adminTracker` |

### Phase 3 — Startup Sequence (`llcRentalTracker`)

| Item | Change | File |
|---|---|---|
| 3a | Replace multi-tier `_inject_secrets()` with single-source; hard fail if `APP_` keys missing | `wsgi.py` |
| 3b | Replace `_inject_env_from_profile()` fallback chain with `APP_` key reads; hard fail | `wsCmd.py` |
| 3c | Reconfigure PA: `--setup` with new code → writes `llcRentalTracker` stanza + `APP_` secrets | PA console |

### Gate 1 — Immediate (no code changes required)

Manual config fixes using current code. See [design_setup_llcRentalTracker.md](design_setup_llcRentalTracker.md).

### Gate 2 — After Phase 2 code merge

Formalize with new code. Same doc.

---

## 7. File Change Summary

| File | Change |
|---|---|
| `pyMultiTaskWS` codebase | Config path `MultiTaskWS_config.json` → `config.json` |
| `pyMultiTaskWS/docs/design_trackerApp.md` | Update §3.5 per-BUS deployment clause; update §3.2 stanza key convention |
| `llcRentalTracker/wsgi.py` | Single-source `_inject_secrets()` with hard fail |
| `llcRentalTracker/wsCmd.py` | `TRACKER_DICT.stanza_key`; `provision_new_bus`; `_write_secrets_to_config`; `setup`; `addTracker`; `_inject_env_from_profile` |
| `llcRentalTracker/ledger/setup_paths.py` | Nested `years:` schema in `find_stanza()`; keep `SECRETS` + `write_secrets()` |
| `llcRentalTracker/docs/design_LLC_01.3-login_auth.md` | Rewrite startup sequence; remove keys.json.gpg; update to `APP_` schema |
| `LLC-WBGroup/books/Accts/` | Remove `keys.json.gpg`; `pw.json.gpg` stays |
| `LLC-WBGroup/books/Accts/llcProfile_WBGroupLLC.json` | Remove `YEAR`, `TOP`, `dirAccounting`, `MultiTaskWS_Config` |
| `~/.llcRentalTracker/config.json` | Remove `master_passphrase`; fix stanza; `APP_` key names |
| `~/.MultiTaskWS/config.json` | Add `llcRentalTracker: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }` |
| `~/.adminTracker/config.json` | Create (convention; initially empty or minimal) |

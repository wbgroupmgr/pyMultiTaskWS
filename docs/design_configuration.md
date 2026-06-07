# Tracker Configuration & Setup — Architecture Guide

> This document covers configuration concepts, the AS-IS → TO-BE action plan, and
> migration ordering for all three repos.
>
> Tracker-specific setup procedures:
> - [design_setup_llcRentalTracker.md](design_setup_llcRentalTracker.md)
> - [design_setup_adminTracker.md](design_setup_adminTracker.md)

--- 

## 1. Design Principles

- **Consistent and elegant above all** — `adminTracker` and `llcRentalTracker` follow the same config and setup pattern
- **Per-tracker config ownership** — each tracker owns its secrets in `~/.<trackerRepo>/config.json`; the platform config holds routing metadata only (no external tracker secrets)
- **No cross-tracker shared secrets** — every tracker has its own unique `APP_GPG_PASSPHRASE` and `APP_SECRET_KEY`; a compromised tracker exposes nothing else
- **No fallback for required artifacts** — if `~/.<trackerRepo>/config.json` is missing `APP_GPG_PASSPHRASE` or `APP_SECRET_KEY`, the app fails immediately with a clear error; no silent substitution
- **PA = master host for BUS data** — only PythonAnywhere pushes commits to `LLC-WBGroup`; all other hosts pull only
- **No tracker references outside its own scope** — `llcRentalTracker` reads its own `~/.llcRentalTracker/config.json`; it does not read another tracker's config or the platform config at runtime

---

## 2. Three-Repo Architecture

Every deployment involves three independent repositories:

| Repo | Purpose | Configurator |
|---|---|---|
| `pyMultiTaskWS` | Web **platform** — dispatcher, adminTracker | `wsCmd.py --setup` |
| `pyMultiTaskWS` | **adminTracker** (built-in) — web administration | `wsCmd.py --setup` (platform setup includes it) |
| `llcRentalTracker` | Rental property LLC accounting tracker **app** | `wsCmd.py --newBus` + `--setup` |
| `LLC-WBGroup` | **BUS data** — accounting JSON DBs, `pw.json.gpg` user DB | `llcRentalTracker wsCmd.py --newBus` |
| `<otherTracker>` | Other tracker app — standalone or hosted | `wsCmd.py --setup` |

NOTE: `adminTracker` is part of the `pyMultiTaskWS` git repo, not a separate repo.

Each git repo is independent by design:
- `llcRentalTracker` can run without `pyMultiTaskWS`
- `LLC-WBGroup` is owned exclusively by the PA master host (no local writes)
- Any tracker can be standalone or hosted under `pyMultiTaskWS`

### 2.1 Hosting — pythonanywhere.com

Each tracker has its own unique login URL:

```
https://<PA_acctID>.pythonanywhere.com/<mount>/login
```

`<PA_acctID>` is the PythonAnywhere account ID. Custom domains can replace this in the future.

---

## 3. Config File Hierarchy

### 3.1 Platform Config — `~/.MultiTaskWS/config.json`

Owned by `pyMultiTaskWS`. Holds platform-level secrets, one `adminTracker` secrets stanza
(built-in tracker), and a routing-only `Trackers` list for external trackers.
Written by `pyMultiTaskWS/wsCmd.py --setup`.

**External trackers (e.g. `llcRentalTracker`) have NO secrets stanza here.** They read
secrets exclusively from their own `~/.<trackerRepo>/config.json`. The platform config
contains only their routing metadata (mount, url, sys_path).

```json
{
  "WEB_GPG_PASSPHRASE": "<platform passphrase — adminTracker user DB>",
  "WEB_SECRET_KEY":     "<platform Flask signing key>",
  "WebServer":          "Host_wbgroup",
  "install_dir":        "<absolute path to pyMultiTaskWS clone on this host>",
  "gitRemote":          "wbgroupmgr/pyMultiTaskWS",
  "adminTracker": {
    "APP_GPG_PASSPHRASE": "<unique — adminTracker pw.json.gpg>",
    "APP_SECRET_KEY":     "<unique random hex>"
  },
  "Trackers": [
    {
      "name":        "adminTracker",
      "stanza_key":  "adminTracker",
      "mount":       "/admin",
      "url":         "/admin/login",
      "description": "Platform administration — user management & tracker index",
      "status":      "online",
      "builtin":     true,
      "sys_path":    "<install_dir>/adminTracker"
    },
    {
      "name":        "LLC Rental Tracker",
      "stanza_key":  "llcRentalTracker",
      "gitRemote":   "wbgroupmgr/llcRentalTracker",
      "mount":       "/rentalTracker",
      "url":         "/rentalTracker/login",
      "description": "Financial Mgmt App for Property Rental LLC",
      "status":      "online",
      "builtin":     false,
      "sys_path":    "<absolute path to llcRentalTracker clone>"
    },
    {
      "name":        "<TrackerDisplayName>",
      "stanza_key":  "<trackerRepo>",
      "gitRemote":   "<git_UserID>/<trackerRepo>",
      "mount":       "/<trackerRepo>",
      "url":         "/<trackerRepo>/login",
      "description": "<one-line description>",
      "status":      "online",
      "builtin":     false,
      "sys_path":    "<absolute path to trackerRepo clone>"
    }
  ]
}
```

- `install_dir` — absolute path where `pyMultiTaskWS` is cloned on this host
- `mount` — URL prefix used by the dispatcher (`/admin`, `/rentalTracker`, etc.)
- `sys_path` — absolute path to the directory containing `wsgi.py` for that tracker
- `adminTracker` stanza holds secrets because it is built-in (platform manages it directly)
- External tracker secrets are NOT in this file — each tracker reads its own `~/.<trackerRepo>/config.json`

`chmod 600` — owner only. **Never committed to git.**

---

### 3.2 Tracker Config — `~/.<trackerRepo>/config.json`

Each tracker owns its own config:

```
~/.adminTracker/config.json       (adminTracker)
~/.llcRentalTracker/config.json   (llcRentalTracker)
```

#### `llcRentalTracker` schema — M BUS × N years

`APP_SECRET_KEY` is **per-tracker** (one Flask signing key for the whole app).
`APP_GPG_PASSPHRASE` is **per-BUS** (each BUS encrypts its own `pw.json.gpg` independently).

```json
{
  "default": ["WBGroupLLC", 2025],
  "APP_SECRET_KEY": "<one key for the llcRentalTracker Flask app>",
  "llcList": [
    {
      "llcName":   "WBGroupLLC",
      "dataName":  "WBGroupLLC",
      "bus_repo":  "<absolute path to LLC-WBGroup>",
      "books_dir": "books",
      "years":     [2025, 2026],
      "APP_GPG_PASSPHRASE": "<unique passphrase — sole key for WBGroupLLC pw.json.gpg>"
    },
    {
      "llcName":   "<otherBUS>",
      "dataName":  "<otherBUS>",
      "bus_repo":  "<absolute path to otherBUS repo>",
      "books_dir": "books",
      "years":     [2025],
      "APP_GPG_PASSPHRASE": "<unique passphrase — different from WBGroupLLC>"
    }
  ]
}
```

`chmod 600`. **Never committed to git.**

The `llcList` is built by `llcRentalTracker wsCmd.py --newBus`. Each call to `--newBus`
adds or updates one BUS stanza. `--newBus` prompts for that BUS's `APP_GPG_PASSPHRASE`
(which must match the passphrase used to encrypt that BUS's `pw.json.gpg`).

---

### 3.3 Per-Tracker Passphrase and SECRET_KEY

| Secret | Config key | Location | Env var injected | Scope |
|---|---|---|---|---|
| Platform GPG | `WEB_GPG_PASSPHRASE` | `~/.MultiTaskWS/config.json` | `WEB_GPG_PASSPHRASE` | platform-wide |
| Platform Flask key | `WEB_SECRET_KEY` | `~/.MultiTaskWS/config.json` | `WEB_SECRET_KEY` | platform-wide |
| adminTracker GPG | `APP_GPG_PASSPHRASE` | `~/.MultiTaskWS/config.json` `adminTracker:` | `APP_GPG_PASSPHRASE` | per-tracker |
| adminTracker Flask key | `APP_SECRET_KEY` | `~/.MultiTaskWS/config.json` `adminTracker:` | `APP_SECRET_KEY` | per-tracker |
| llcRentalTracker Flask key | `APP_SECRET_KEY` | `~/.llcRentalTracker/config.json` (top-level) | `LLC_SECRET_KEY` | per-tracker |
| llcRentalTracker GPG | `APP_GPG_PASSPHRASE` | `~/.llcRentalTracker/config.json` `llcList[i]` | `LLC_GPG_PASSPHRASE` | **per-BUS** |

**Runtime injection rule:** `llcRentalTracker` startup reads `APP_SECRET_KEY` from the top-level
config and `APP_GPG_PASSPHRASE` from the active BUS's `llcList` stanza. No fallback to the
platform config. Missing either key → immediate hard failure.

---

## 4. Target Architecture (TO-BE)

```
~/.MultiTaskWS/config.json          (platform — never in git)
  WEB_GPG_PASSPHRASE, WEB_SECRET_KEY, install_dir, gitRemote
  adminTracker: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }
  Trackers: [ adminTracker (routing), llcRentalTracker (routing only), ... ]

~/.adminTracker/config.json         (adminTracker — never in git)
  minimal metadata; secrets live in ~/.MultiTaskWS/config.json adminTracker stanza

~/.llcRentalTracker/config.json     (llcRentalTracker — never in git)
  APP_SECRET_KEY                    (per-tracker Flask signing key)
  llcList: [
    { WBGroupLLC, bus_repo, years, APP_GPG_PASSPHRASE },   ← per-BUS
    { otherBUS,   bus_repo, years, APP_GPG_PASSPHRASE },   ← per-BUS
  ]

LLC-WBGroup repo (BUS data):
  books/Accts/*.json                accounting data
  books/Accts/pw.json.gpg           BUS-specific user DB — PA=master-push only
  (keys.json.gpg REMOVED — replaced by per-BUS APP_GPG_PASSPHRASE in llcList stanza)

<otherBUS> repo:
  books/Accts/pw.json.gpg           encrypted with otherBUS APP_GPG_PASSPHRASE
```

**What is removed in the TO-BE state:**
- `keys.json.gpg` from each BUS repo — replaced by `llcList[i].APP_GPG_PASSPHRASE` in tracker config
- `master_passphrase` from `~/.llcRentalTracker/config.json` — no longer needed
- `MultiTaskWS_Config` block from `llcProfile_WBGroupLLC.json` — entity data only remains
- Stale `LLC_GPG_PASSPHRASE`/`LLC_SECRET_KEY` key names — renamed to `APP_GPG_PASSPHRASE`/`APP_SECRET_KEY`
- `secrets:` nested block in llcList stanza — flattened to `APP_GPG_PASSPHRASE` directly in stanza

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
4. The current `LLC_GPG_PASSPHRASE` on PA becomes the new `APP_GPG_PASSPHRASE` — record it first so `pw.json.gpg` decrypts without user re-registration

### 5.3 Clean-Slate vs. In-Place Migration

**Clean-slate is recommended** for this migration. In-place migration risks leaving
stale config keys that confuse the new code. The clean-slate procedure:

1. Record current secrets (before deleting anything)
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
| 2b | `provision_new_bus()`: prompt `APP_GPG_PASSPHRASE` per BUS; store in `llcList[i]`; remove keys.json.gpg logic | `wsCmd.py` |
| 2b | `_write_secrets_to_config()`: write `APP_SECRET_KEY` at top level; `APP_GPG_PASSPHRASE` per stanza | `wsCmd.py` |
| 2b | `setup()`: remove `_ensure_keys()` block; read `APP_SECRET_KEY` from top-level; `APP_GPG_PASSPHRASE` from active BUS stanza | `wsCmd.py` |
| 2b | `addTracker()`: write routing-only entry to platform `Trackers` list (no secrets stanza) | `wsCmd.py` |
| 2c | Remove `keys.json.gpg` from BUS repos; remove `master_passphrase` | `LLC-WBGroup` + `wsCmd.py` |
| 2d | Fix duplicate stanza; fix `llcName: "LLC-WBGroup"` → `"WBGroupLLC"`; nested `years:` + flat `APP_GPG_PASSPHRASE` per stanza | `setup_paths.py` |
| 2e | Add per-BUS deployment clause to `design_trackerApp.md §3.5` | `pyMultiTaskWS` docs |
| 2f | Create `~/.adminTracker/config.json` convention | `adminTracker` |

### Phase 3 — Startup Sequence (`llcRentalTracker`)

| Item | Change | File |
|---|---|---|
| 3a | Replace multi-tier `_inject_secrets()` with single-source: `APP_SECRET_KEY` (top-level) + `APP_GPG_PASSPHRASE` (active BUS stanza); hard fail if missing | `wsgi.py` |
| 3b | Replace `_inject_env_from_profile()` fallback chain with same single-source reads; hard fail | `wsCmd.py` |
| 3c | Reconfigure PA: `--setup` with new code → writes per-BUS `APP_GPG_PASSPHRASE` + top-level `APP_SECRET_KEY` | PA console |

### Gate 1 — Immediate (no code changes required)

Manual config fixes using current code. See [design_setup_llcRentalTracker.md](design_setup_llcRentalTracker.md).

### Gate 2 — After Phase 2 code merge

Formalize with new code. Same doc.

---

## 7. File Change Summary

| File | Change |
|---|---|
| `pyMultiTaskWS` codebase | Config path `MultiTaskWS_config.json` → `config.json`; `Trackers` routing-only for external trackers |
| `pyMultiTaskWS/docs/design_trackerApp.md` | Update §3.5 per-BUS deployment clause; update §3.2 stanza key convention |
| `llcRentalTracker/wsgi.py` | Single-source `_inject_secrets()`: `APP_SECRET_KEY` top-level + `APP_GPG_PASSPHRASE` from active BUS stanza; hard fail |
| `llcRentalTracker/wsCmd.py` | `TRACKER_DICT.stanza_key`; `provision_new_bus` per-BUS passphrase; `_write_secrets_to_config` (top-level `APP_SECRET_KEY`); `setup`; `addTracker` routing-only; `_inject_env_from_profile` |
| `llcRentalTracker/ledger/setup_paths.py` | Nested `years:` + flat `APP_GPG_PASSPHRASE` per stanza; `APP_SECRET_KEY` at top level; update `SECRETS` population |
| `llcRentalTracker/docs/design_LLC_01.3-login_auth.md` | Rewrite startup sequence; remove keys.json.gpg; update to M-BUS per-stanza schema |
| `LLC-WBGroup/books/Accts/` | Remove `keys.json.gpg`; `pw.json.gpg` stays |
| `LLC-WBGroup/books/Accts/llcProfile_WBGroupLLC.json` | Remove `YEAR`, `TOP`, `dirAccounting`, `MultiTaskWS_Config` |
| `~/.llcRentalTracker/config.json` | Remove `master_passphrase`; `APP_SECRET_KEY` top-level; `APP_GPG_PASSPHRASE` flat in each `llcList` stanza |
| `~/.MultiTaskWS/config.json` | Routing-only Trackers list; `adminTracker` secrets stanza only; no external tracker secrets |
| `~/.adminTracker/config.json` | Create (convention; initially minimal metadata) |

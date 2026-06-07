# Tracker Config & Secrets Setup — Architecture Assessment & Action Plan

## Context

Full multi-layer architecture assessment covering `pyMultiTaskWS`, `llcRentalTracker`, and
`LLC-WBGroup` (BUS) data repo. Phase 1 (startup crash fix) is already merged in
`llcRentalTracker@a47da23`. This document tracks Phases 2–3.

**Guiding Principles**
- Consistent and elegant above all
- `adminTracker` and `llcRentalTracker` follow the same config/setup pattern
- `adminTracker` gets its own `~/.adminTracker/config.json`
- Platform config renamed to `~/.MultiTaskWS/config.json`
- No tracker references internals outside its own codebase / `~/<tracker>/config.json`
- No shortcuts — strict OO discipline, reuse

---

## Design Documents Reviewed

- `pyMultiTaskWS/docs/design_trackerApp.md` — MultiTaskWS tracker contract
- `llcRentalTracker/docs/design_LLC_01.3-login_auth.md` — llcRentalTracker auth design

---

## Current State (PA + Local)

### PA `~/.llcRentalTracker/config.json`
```json
{
  "default": ["WBGroupLLC", 2025],
  "llcList": [
    { "llcName": "LLC-WBGroup", ... },   // BUG: wrong llcName (repo name, not LLC ID)
    { "llcName": "WBGroupLLC",  ... }    // correct — but duplicate stanza
  ],
  "master_passphrase": "..."             // REMOVE: only needed for keys.json.gpg (going away)
}
```
- Duplicate stanza; one with wrong `llcName: "LLC-WBGroup"` (git repo name ≠ LLC identifier)
- No `secrets` block → `setup_paths.SECRETS = {}` → startup crash (Phase 1 fixed symptom)
- See also: `llcRentalTracker #19` for the M BUS × N Years flat-to-nested schema refactor

### PA `~/.MultiTaskWS/MultiTaskWS_config.json`
- Has `adminTracker` stanza with `APP_GPG_PASSPHRASE` + `WEB_SECRET_KEY` ✓
- Has `llcRentalTracker` in `Trackers` list but **no `llcRentalTracker` credentials stanza** ✗
- `WEB_GPG_PASSPHRASE` at top level is the platform-wide passphrase (not tracker-specific)

---

## Bugs

### Bug 1 — `llcRentalTracker` credentials stanza MISSING from platform config

Per `design_trackerApp.md §3.2`, `wsCmd.py --setup` must write a tracker stanza to the
platform config so the platform can inject the tracker's secrets as env vars:

```json
"llcRentalTracker": {
  "APP_GPG_PASSPHRASE": "...",
  "APP_SECRET_KEY": "..."
}
```

This stanza is missing on PA. Every workaround layered on top — secrets in the profile
JSON, `keys.json.gpg`, `secrets` block in `~/.llcRentalTracker/config.json` — exists
solely to compensate for this missing stanza. Fixing Bug 1 makes most workarounds
unnecessary.

### Bug 2 — Duplicate + wrong `llcName` in `~/.llcRentalTracker/config.json`

`"llcName": "LLC-WBGroup"` is the git repo folder name, not the LLC business identifier.
Should be `"WBGroupLLC"`. The duplicate stanza causes ambiguous `find_stanza()` resolution.
See `llcRentalTracker #19` for the full M BUS × N Years schema fix.

---

## Design Assessments

### Design 1 — `pw.json.gpg` location

**Deployment model: one PA host account per BUS (LLC)**

```
WBGroup.pythonanywhere.com            LLC2.pythonanywhere.com
  BUS: LLC-WBGroup repo                 BUS: LLC2 repo
  users: WBGroup admins only            users: LLC2 admins only
  pw.json.gpg ← WBGroup-specific        pw.json.gpg ← LLC2-specific
```

Each LLC has its own PA account, URL, user database, and BUS data repo. `pw.json.gpg`
is BUS-instance-specific — it must NOT live in `llcRentalTracker` because that would
force all LLC deployments to share one user database. LLC#1's admins have nothing to do
with LLC#2's admins.

**`pw.json.gpg` correctly belongs in the BUS repo.** The PA=master / local=pull-only
rule is the right sync mechanism.

**The actual flaw is in `design_trackerApp.md §3.5`**, which says to gitignore `*.gpg`.
That rule applies to a multi-tenant platform with unrelated deployments. It does not
account for the per-LLC deployment model where the app code is shared but each BUS
instance owns its own user DB. Required fix to `design_trackerApp.md §3.5`:

> **Per-BUS deployment model:** When a tracker is deployed one-instance-per-BUS, each
> BUS has its own host account, URL, and user set. `pw.json.gpg` belongs in the BUS data
> repo — not the tracker app repo. The PA=master-push rule governs who may commit it.
> Do NOT add `Accts/*.gpg` to the tracker app's `.gitignore` in this model.

### Design 2 — `keys.json.gpg` is a non-standard workaround

`keys.json.gpg` (in `LLC-WBGroup/books/Accts/`) does not exist in the MultiTaskWS
contract. It was invented to distribute `APP_GPG_PASSPHRASE` and `APP_SECRET_KEY` across
hosts because the `llcRentalTracker` platform stanza (Bug 1) was never written. Once Bug 1
is fixed, the platform stanza is the canonical source for these secrets and `keys.json.gpg`
is redundant.

**Remove `keys.json.gpg` from the BUS repo.** The `master_passphrase` (which only existed
to decrypt it) is also removed.

### Design 3 — Managing passphrase and SECRET_KEY

**Each tracker requires its own unique `GPG_PASSPHRASE` and `SECRET_KEY`.** Two reasons:

1. **GPG passphrase** — each tracker encrypts its own `pw.json.gpg`. A shared passphrase
   means a compromised tracker exposes all others' user databases. The existing
   `adminTracker` pattern proves this is intentional: `APP_GPG_PASSPHRASE` for adminTracker
   is deliberately different from `APP_GPG_PASSPHRASE` for llcRentalTracker.

2. **Flask `SECRET_KEY`** — signs session cookies. Shared keys make a session token from
   one tracker cryptographically valid in another — a direct security vulnerability.

The `secrets` block in `~/.llcRentalTracker/config.json` is therefore **correct** — it
holds the tracker's own unique secrets. It serves as the **standalone-mode equivalent**
of the `llcRentalTracker` platform stanza:

**Per Tracker Configuration**
It is important to understand there is a unique passphrase `per TRACKER` configuration to manage the TRACKER's respective pw.json.gpg

|Passphrase	|Name	|Where	|How set|
| ===== | ===== | ===== | ===== |
|MultiTaskWS | 	WEB_GPG_PASSPHRASE	| ~/.MultiTaskWS/config.json| Prompted: cd pyTracker; python3 wsCmd.py --setup (platform setup)|
|MultiTaskWS | 	WEB_SECRET_KEY	| ~/.MultiTaskWS/config.json| stanza generated randomly at setup; python3 wsCmd.py --setup (platform setup)|
| ===== | ===== | ===== | ===== |
|<TRACKER> GPG|APP_GPG_PASSPHRASE|~/.<TRACKER>/config.json| Prompted: cd pyTracker/<TRACKER>; python3 wsCmd.py --setup (platform setup)|
|<TRACKER> SECRET|APP_SECRET_KEY|~/.<TRACKER>/config.json|Tracker stanza generated randomly at setup|

**Actual Configuration (TOBE)**

|Passphrase	|Name	|Where	|How set|
| ===== | ===== | ===== | ===== |
|adminTracker GPG|APP_GPG_PASSPHRASE|~/.adminTracker/config.json| Prompted: cd pyTracker/adminTracker; python3 wsCmd.py --setup (platform setup)|
|adminTracker SECRET|APP_SECRET_KEY	|~/.adminTracker/config.json|Tracker stanza	Generated randomly at setup|
| ===== | ===== | ===== | ===== |
|llcRentalTracker GPG|APP_GPG_PASSPHRASE|~/.llcRentalTracker/config.json| Prompted: cd pyTracker/llcRentalTracker; python3 wsCmd.py --setup (platform setup)|
|llcRentalTracker SECRET|APP_SECRET_KEY	|~/.llcRentalTracker/config.json|Tracker stanza	Generated randomly at setup|

**NOTES**:

- In the TO-BE configuarition for both `host` (PA) and `local` the source for passphrase and SECRET_KEY are the same - use of the ~/.<TRACKER>/config.json

#### Passphrase & SECRET_KEY — Runtime injection priority

There is no fallback or runtime injection priority.
Key design rule: no shortcuts and NO FALLBACK for artifacts that are required.
The ~/.<TRACKER>/config.json is the sole authority.

---

## Operational Workflows

Ordered from initial PA account acquisition to daily operations.
Each workflow is self-contained with exact commands.

---

### Workflow 1 — New PA Instance: Full Platform + Tracker Setup

**Prerequisites**
- PA account created; console access available
- GitHub repos exist: `pyMultiTaskWS`, `llcRentalTracker`, `LLC-WBGroup`
- `gpg` and `python3.10+` available on PA

---

#### Step 1 — Setup MultiTaskWS Platform

```bash
# Clone platform repo
cd 
git clone https://github.com/wbgroupmgr/pyMultiTaskWS.git
cd pyMultiTaskWS

# Bootstrap platform — creates ~/.MultiTaskWS/config.json
# Generates WEB_SECRET_KEY; registers platform Trackers list
python3 wsCmd.py --setup
# → prompts: Enter platform WEB_SECRET_KEY (or auto-generate?)
# → writes ~/.MultiTaskWS/config.json:
#     { WEB_SECRET_KEY, Trackers: [] }

# Point PA WSGI file to:  /home/<user>/pyMultiTaskWS/wsgi.py
# (PA dashboard → Web tab → WSGI configuration file)
```\
**State after Step 1**
```
~/.MultiTaskWS/config.json
  WEB_SECRET_KEY: "<generated>"
  Trackers: []
```

---

#### Step 2 — Setup adminTracker
\
h
cd ~/pyMultiTaskWS

python3 adminTracker/wsCmd.py --setup
# → generates unique APP_GPG_PASSPHRASE (distinct from all other trackers)
# → generates unique WEB_SECRET_KEY for adminTracker
# → writes adminTracker stanza to ~/.MultiTaskWS/config.json
# → creates ~/.adminTracker/config.json
# → creates adminTracker/Accts/pw.json.gpg  (seed user: admin / change immediately)
# → registers adminTracker in Trackers list
```

**State after Step 2**
```
~/.MultiTaskWS/config.json
  WEB_SECRET_KEY: "<platform key>"
  Trackers: [ { name: AdminTracker, stanza_key: adminTracker, ... } ]
  adminTracker: {
    APP_GPG_PASSPHRASE: "<unique passphrase>",
    WEB_SECRET_KEY:     "<unique key>"
  }

~/.adminTracker/config.json   (created; tracker-specific non-secret config)

pyMultiTaskWS/adminTracker/Accts/pw.json.gpg   (seed user — change password now)
```

Login at `https://<pa-domain>/admin/login` → change seed password immediately.

---

#### Step 3 — Clone BUS Repo

```bash
mkdir ~/llc && cd ~/llc
git clone https://github.com/wbgroupmgr/LLC-WBGroup.git
# BUS data now at:  ~/llc/LLC-WBGroup/books/Accts/
```

---

#### Step 4 — Setup llcRentalTracker

```bash
mkdir ~/pyTrackers && cd ~/pyTrackers
git clone https://github.com/wbgroupmgr/llcRentalTracker.git
cd llcRentalTracker
```

**4a — Register BUS + set tracker passphrase**

```bash
python3 wsCmd.py --newBus ~/llc/LLC-WBGroup --year 2025 --llcName WBGroupLLC
# → prompts: Enter APP_GPG_PASSPHRASE for this tracker (unique; not shared with adminTracker)
# → creates ~/.llcRentalTracker/config.json  (if absent):
#     { default: [WBGroupLLC, 2025],
#       llcList: [{ llcName: WBGroupLLC, bus_repo: ~/llc/LLC-WBGroup,
#                   books_dir: books, years: [2025] }],
#       secrets: { APP_GPG_PASSPHRASE: "<entered>" }
#     }
# → sets default to WBGroupLLC/2025
```

**4b — Setup tracker secrets + user DB**

```bash
python3 wsCmd.py --setup --llcName WBGroupLLC
# → reads APP_GPG_PASSPHRASE from ~/.llcRentalTracker/config.json secrets: (set by --newBus)
# → generates APP_SECRET_KEY
# → writes complete secrets: { APP_GPG_PASSPHRASE, APP_SECRET_KEY } to ~/.llcRentalTracker/config.json
# → writes llcRentalTracker stanza to ~/.MultiTaskWS/config.json:
#     llcRentalTracker: { APP_GPG_PASSPHRASE: <APP_GPG_PASSPHRASE value>, APP_SECRET_KEY: <APP_SECRET_KEY value> }
#     (tracker env var names in platform stanza; values sourced from tracker config)
# → registers llcRentalTracker in Trackers list in ~/.MultiTaskWS/config.json
# → creates BUS/books/Accts/pw.json.gpg  (seed user: llcgroupmgr / change immediately)
# → prints: "Push pw.json.gpg to BUS repo now (PA = master host)"

# Push pw.json.gpg — PA is the master host for the BUS repo
cd ~/llc/LLC-WBGroup
git add books/Accts/pw.json.gpg
git commit -m "auth: initial user DB"
git push
cd ~/pyTrackers/llcRentalTracker
```

**State after Step 4b**
```
~/.MultiTaskWS/config.json
  WEB_SECRET_KEY: "<platform key>"
  Trackers: [ adminTracker, llcRentalTracker ]
  adminTracker:   { APP_GPG_PASSPHRASE, WEB_SECRET_KEY }
  llcRentalTracker:  { APP_GPG_PASSPHRASE, APP_SECRET_KEY }   ← NEW

~/.llcRentalTracker/config.json
  default: [WBGroupLLC, 2025]
  llcList: [{ llcName: WBGroupLLC, bus_repo: ..., books_dir: books, years: [2025] }]
  secrets: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }          ← SOLE authority (no fallback)

LLC-WBGroup/books/Accts/pw.json.gpg   (in BUS repo, pushed — seed user)
```

**4c — Reload PA / verify**

```bash
# PA Web tab → Reload
# Visit https://<pa-domain>/llcRentalTracker/login
# Login: llcgroupmgr / llcManager0!  → change password immediately
```

**4c (standalone) — Start for local testing**

```bash
python3 wsCmd.py --start --llcName WBGroupLLC --year 2025 --port 5000 --load
# → reads APP_GPG_PASSPHRASE + APP_SECRET_KEY from ~/.llcRentalTracker/config.json secrets:
#   (sole source — no tier fallback; fails immediately if either is missing)
# → injects APP_GPG_PASSPHRASE + APP_SECRET_KEY into os.environ
# → starts Flask at http://localhost:5000/llcRentalTracker
```

---

### Workflow 2 — Local Dev Setup (after PA is running)

```bash
# Clone both repos
git clone https://github.com/wbgroupmgr/llcRentalTracker.git
git clone https://github.com/wbgroupmgr/LLC-WBGroup.git

cd llcRentalTracker

# Register BUS at the local path (same llcName, same passphrase as PA)
python3 wsCmd.py --newBus /path/to/LLC-WBGroup --year 2025 --llcName WBGroupLLC
# → prompts for APP_GPG_PASSPHRASE — enter the SAME value used on PA
#   (same passphrase required to decrypt pw.json.gpg pulled from the BUS repo)
# → creates ~/.llcRentalTracker/config.json with local bus_repo path + secrets: { APP_GPG_PASSPHRASE }

python3 wsCmd.py --setup --llcName WBGroupLLC
# → reads APP_GPG_PASSPHRASE from ~/.llcRentalTracker/config.json secrets: (set by --newBus)
# → generates APP_SECRET_KEY; writes complete secrets: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }
# → does NOT write platform stanza (no ~/.MultiTaskWS/ in standalone dev mode)
# → does NOT create pw.json.gpg (pull from BUS repo — local never writes it)

# Pull pw.json.gpg from PA-committed BUS repo
cd /path/to/LLC-WBGroup && git pull
cd /path/to/llcRentalTracker

# Start local
python3 wsCmd.py --start --llcName WBGroupLLC --year 2025 --port 5000 --load
```

**Key rule:** Local dev never pushes `pw.json.gpg` to the BUS repo.
User management happens on PA only.

---

### Workflow 3 — Add a New Fiscal Year (e.g. 2026)

```bash
# On PA:
cd ~/pyTrackers/llcRentalTracker
python3 wsCmd.py --newBus ~/llc/LLC-WBGroup --year 2026 --llcName WBGroupLLC
# → appends 2026 to existing WBGroupLLC stanza: years: [2025, 2026]
# → no new stanza created (same bus_repo, same passphrase)
# → no pw.json.gpg changes

# PA Web tab → Reload
# Switch year in app UI, or:
python3 wsCmd.py --start --llcName WBGroupLLC --year 2026 --port 5000

# Local: same command with local path
python3 wsCmd.py --newBus /path/to/LLC-WBGroup --year 2026 --llcName WBGroupLLC
```

---

### Workflow 4 — Add a Second BUS (new LLC)

```bash
# On PA: clone or create new BUS repo
cd ~/llc && git clone https://github.com/owner/LLC2.git

cd ~/pyTrackers/llcRentalTracker
python3 wsCmd.py --newBus ~/llc/LLC2 --year 2025 --llcName LLC2Name
# → prompts for LLC2's APP_GPG_PASSPHRASE (NEW unique passphrase — not shared with WBGroupLLC)
# → adds LLC2Name stanza to ~/.llcRentalTracker/config.json llcList
# → does NOT overwrite WBGroupLLC stanza

python3 wsCmd.py --setup --llcName LLC2Name
# → creates LLC2/books/Accts/pw.json.gpg encrypted with LLC2's passphrase
# → NOTE: llcRentalTracker platform stanza holds ONE tracker's secrets
#   If multiple BUS instances are deployed as separate PA accounts (one per BUS),
#   each PA account runs its own wsCmd.py --setup with its own stanza.
#   A single PA account running multiple BUS instances is not yet supported.

# Push LLC2 pw.json.gpg from PA
cd ~/llc/LLC2
git add books/Accts/pw.json.gpg && git commit -m "auth: initial user DB" && git push
```

---

### Workflow 5 — Key Rotation

```bash
# On PA — generates new APP_GPG_PASSPHRASE + APP_SECRET_KEY
cd ~/pyTrackers/llcRentalTracker
python3 wsCmd.py --rotate-keys --llcName WBGroupLLC
# → prompts: Enter new APP_GPG_PASSPHRASE
# → re-encrypts BUS/books/Accts/pw.json.gpg with new passphrase
# → updates llcRentalTracker stanza in ~/.MultiTaskWS/config.json (APP_GPG_PASSPHRASE env var name)
# → updates secrets: APP_GPG_PASSPHRASE + APP_SECRET_KEY in ~/.llcRentalTracker/config.json

# Push rotated pw.json.gpg
cd ~/llc/LLC-WBGroup
git add books/Accts/pw.json.gpg && git commit -m "auth: rotate keys" && git push

# PA Web tab → Reload

# All other hosts: git pull BUS repo + re-run --setup with new passphrase
git pull
python3 wsCmd.py --setup --llcName WBGroupLLC   # enter new APP_GPG_PASSPHRASE when prompted
```

### Design Flaw 4 — Naming inconsistency across layers

| What | Where | Name |
|---|---|---|
| GPG passphrase (platform-wide) | `~/.MultiTaskWS/config.json` | `WEB_GPG_PASSPHRASE` |
| GPG passphrase (llcRentalTracker) | env var + stanza | `APP_GPG_PASSPHRASE` |
| GPG passphrase (adminTracker) | `~/.MultiTaskWS/config.json` adminTracker stanza | `APP_GPG_PASSPHRASE` |
| Flask secret (platform) | `~/.MultiTaskWS/config.json` | `WEB_SECRET_KEY` |
| Flask secret (llcRentalTracker) | env var + stanza | `APP_SECRET_KEY` |
| Flask secret (adminTracker stanza) | `~/.MultiTaskWS/config.json` | `WEB_SECRET_KEY` |

Per `design_trackerApp.md §3.2`, the convention is `<TRACKER>_GPG_PASSPHRASE` /
`<TRACKER>_SECRET_KEY` where `<TRACKER>` matches the tracker slug (§3.6: short lowercase).
Recommendation: formalize `llc` as the llcRentalTracker slug → `APP_GPG_PASSPHRASE` and
`APP_SECRET_KEY` are then correctly formed and consistent.

### Design Flaw 5 — Platform config path naming

- Current: `~/.MultiTaskWS/MultiTaskWS_config.json`
- Required: `~/.MultiTaskWS/config.json`

All code references must be updated across `pyMultiTaskWS`, `llcRentalTracker`, and
`adminTracker`.

### Design Flaw 6 — adminTracker has no `~/.adminTracker/config.json`

`llcRentalTracker` has `~/.llcRentalTracker/config.json` for tracker-specific non-secret
config. For consistency, `adminTracker` should have `~/.adminTracker/config.json`. Since
adminTracker is a built-in tracker this may be intentionally empty, but the file and
convention should exist explicitly.

---

## Target Architecture

```
~/.MultiTaskWS/config.json                       ← RENAMED from ~/.MultiTaskWS/MultiTaskWS_config.json
  WEB_SECRET_KEY                               platform Flask signing key
  Trackers: [...]                              registered tracker list
  adminTracker: {                              built-in tracker stanza
    APP_GPG_PASSPHRASE: "..._adminTracker",
    APP_SECRET_KEY: "..."
  }
  llcRentalTracker: {                             external tracker stanza (CURRENTLY MISSING — Bug 1)
    APP_GPG_PASSPHRASE: "...",
    APP_SECRET_KEY: "..."
  }

~/.adminTracker/config.json                    ← NEW (consistency with per-tracker config pattern)

~/.llcRentalTracker/config.json                ← CLEANED
  default, llcList (nested M BUS × N years)    keep — see llcRentalTracker #19
  secrets: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }  PRIMARY + SOLE source (Design 3)
  master_passphrase                            REMOVE — only needed for keys.json.gpg

LLC-WBGroup repo (BUS data):
  books/Accts/*.json                           accounting data — unchanged
  books/Accts/pw.json.gpg                      STAYS — BUS-specific user DB, PA=master-push
  books/Accts/keys.json.gpg                    REMOVE — replaced by platform stanza (Bug 1 fix)
```

---

## Action Plan

### Phase 2 — Config & Contract Alignment

**2a — Rename platform config path** (`pyMultiTaskWS`)
- Rename `~/.MultiTaskWS/MultiTaskWS_config.json` → `~/.MultiTaskWS/config.json` (file rename only; directory stays)
- Update all references in `pyMultiTaskWS`, `llcRentalTracker`, `adminTracker`
- Update `wsgi.py _inject_secrets()` — remove MultiTaskWS fallback path (replaced by Phase 3a single-source)

**2b — Write `llcRentalTracker` stanza in `wsCmd.py --setup`; standardize to `APP_` key names** (`llcRentalTracker`)
- `wsCmd.py --newBus`: prompt for `APP_GPG_PASSPHRASE`; write `secrets: { APP_GPG_PASSPHRASE }` to `~/.llcRentalTracker/config.json`
- `wsCmd.py --setup`: read `APP_GPG_PASSPHRASE` from `_sp.SECRETS`; generate `APP_SECRET_KEY`; write both to `secrets:` block
- `wsCmd.py --setup`: write platform stanza to `~/.MultiTaskWS/config.json` (if present) using tracker env var names: `llcRentalTracker: { APP_GPG_PASSPHRASE: <APP value>, APP_SECRET_KEY: <APP value> }`
- Remove `_ensure_master_passphrase()` and `_ensure_keys()` calls from `provision_new_bus()`; remove `--F` keys.json.gpg logic
- Remove code that writes secrets to `llcProfile_*.json`
- Keep `write_secrets()` in `setup_paths.py` and `SECRETS` global — consumers updated to use `APP_` key names

Code change details — `llcRentalTracker/wsCmd.py`:
- `provision_new_bus()`: replace `_ensure_master_passphrase()` + `_ensure_keys()` with direct `_prompt_passphrase_pair("APP_GPG_PASSPHRASE")`; write to `config.json secrets:` via `_sp.write_secrets()`
- `_write_secrets_to_config()`: rename dict keys `APP_SECRET_KEY` → `APP_SECRET_KEY`, `APP_GPG_PASSPHRASE` → `APP_GPG_PASSPHRASE`; keep `WebServer` tag
- `setup()`: remove `keys_file` / `_ensure_keys()` block entirely; read `APP_GPG_PASSPHRASE` from `_sp.SECRETS` (written by `--newBus`); call `_write_secrets_to_config()` to add `APP_SECRET_KEY`
- `addTracker()`: write `llcRentalTracker` stanza to MultiTaskWS config using tracker env var names sourced from `_sp.SECRETS` `APP_` values

**2c — Remove `keys.json.gpg`** (`llcRentalTracker` + `LLC-WBGroup`)
- Remove `keys.json.gpg` from BUS repo (`LLC-WBGroup/books/Accts/`)
- Remove `master_passphrase` from `~/.llcRentalTracker/config.json`
- Remove all `keys.json.gpg` decrypt code from `wsCmd.py`, `wsgi.py`, `setup_paths.py`
- Update `design_LLC_01.3-login_auth.md`

**2d — Fix `~/.llcRentalTracker/config.json` schema** (`llcRentalTracker #19`)
- Remove duplicate stanza; fix `llcName: "LLC-WBGroup"` → `"WBGroupLLC"`
- Migrate flat `llcList` to nested M BUS × N years format
- Remove `master_passphrase`

**2e — Fix `design_trackerApp.md §3.5`** (`pyMultiTaskWS`)
- Add per-BUS deployment clause: `pw.json.gpg` belongs in BUS repo in this model;
  do NOT gitignore `Accts/*.gpg` in the tracker app repo

**2f — Create `~/.adminTracker/config.json` convention** (`adminTracker`)
- Define the file (may be empty initially); document its purpose

### Phase 3 — Startup Sequence

**3a — `wsgi.py` startup secrets injection** (`llcRentalTracker`)
Replace multi-tier fallback with single-source injection. `~/.llcRentalTracker/config.json secrets:` is
the sole authority. Hard `RuntimeError` if either key is missing — no silent fallback, no setdefault on empty string:
```python
# SOLE SOURCE: ~/.llcRentalTracker/config.json secrets:
# APP_GPG_PASSPHRASE → APP_GPG_PASSPHRASE env var (tracker's internal env var name)
# APP_SECRET_KEY     → APP_SECRET_KEY env var
_s  = _sp.SECRETS
_pp = _s.get("APP_GPG_PASSPHRASE", "")
_sk = _s.get("APP_SECRET_KEY", "")
if not _pp or not _sk:
    raise RuntimeError(
        f"[wsgi] FATAL: APP_GPG_PASSPHRASE/APP_SECRET_KEY missing from {_sp.CONFIG_FILE} secrets:\n"
        "  Run: python3 wsCmd.py --setup --llcName <name>"
    )
os.environ.setdefault("APP_GPG_PASSPHRASE", _pp)
os.environ.setdefault("APP_SECRET_KEY", _sk)
```

Code change details — `llcRentalTracker/wsgi.py`:
- Remove entire `_inject_secrets()` function body (all tier logic + try/except)
- Replace with above single-source block (no tier numbering, no MultiTaskWS fallback)
- No `os.environ` check before reading config — config is always the source

**3b — `wsCmd.py --start` injection** (`llcRentalTracker`)
Same single-source pattern as `wsgi.py` — no platform-vs-standalone distinction.
`~/.<TRACKER>/config.json` is the sole source in both modes.

Code change details — `llcRentalTracker/wsCmd.py` `_inject_env_from_profile()`:
- Replace `cfg = _sp.SECRETS or {}` → `cfg = _sp.SECRETS`
- Replace `APP_GPG_PASSPHRASE` key reads → `APP_GPG_PASSPHRASE`; `APP_SECRET_KEY` → `APP_SECRET_KEY`
- Remove `MultiTaskWS_Config` fallback block entirely
- `sys.exit()` with explicit error message if `APP_GPG_PASSPHRASE` or `APP_SECRET_KEY` is missing

**3c — Reconfigure PA**
1. `git pull` both repos
2. Run `wsCmd.py --setup` with updated code → writes `llcRentalTracker` stanza + `secrets:`
3. Reload PA web app

---

### Workflow 6 — Reset Host Configuration: Current → Target State

Migrates both PA and local from the current messy state to the target architecture.
Divided into two gates: **Now** (manual edits, no code changes needed) and
**After Phase 2** (requires new code in `llcRentalTracker`).

---

#### Current State Snapshot

**Preserve these values — read them from the current PA profile before changing anything:**

| Value | Source (current) | Notes |
|---|---|---|
| `APP_GPG_PASSPHRASE` | PA `llcProfile MultiTaskWS_Config.APP_GPG_PASSPHRASE` | **PA value is canonical** — local has a typo (extra space) |
| `APP_SECRET_KEY` | PA `llcProfile MultiTaskWS_Config.APP_SECRET_KEY` | Used for Flask sessions |
| `adminTracker.APP_GPG_PASSPHRASE` | PA `~/.MultiTaskWS/MultiTaskWS_config.json` | Do not change |
| `adminTracker.WEB_SECRET_KEY` | PA `~/.MultiTaskWS/MultiTaskWS_config.json` | Do not change |
| `WEB_SECRET_KEY` (platform) | PA `~/.MultiTaskWS/MultiTaskWS_config.json` | Do not change |
| `master_passphrase` | PA `~/.llcRentalTracker/config.json` | Remove after migration |

```bash
# On PA — read and record values before editing anything
python3 -c "
import json
from pathlib import Path
p = Path('/home/wbgroup/llc/LLC-WBGroup/books/Accts/llcProfile_WBGroupLLC.json')
cfg = json.loads(p.read_text())
mw = cfg.get('MultiTaskWS_Config', {})
print('APP_GPG_PASSPHRASE:', mw.get('APP_GPG_PASSPHRASE'))
print('APP_SECRET_KEY    :', mw.get('APP_SECRET_KEY'))
"
```

**Known inconsistency — fix during migration:**
Local `~/.llcRentalTracker/config.json` secrets has `"APP_GPG_PASSPHRASE": "mylord,myredeemer, myrock"` (extra space). PA profile has `"mylord,myredeemer,myrock"` (no space). PA value is authoritative — local must be corrected to match.

---

#### Gate 1 — Now (no code changes required)

These steps use the current `llcRentalTracker@a47da23` code. The Phase 1 fix already
reads `~/.MultiTaskWS/MultiTaskWS_config.json` as Tier 3, so the rename can wait until
Phase 2a code lands.

**PA: Step 1 — Add missing `llcRentalTracker` stanza to MultiTaskWS config**

Edit `~/.MultiTaskWS/MultiTaskWS_config.json` — add the stanza (using PA canonical values):

```json
"llcRentalTracker": {
  "APP_GPG_PASSPHRASE": "<value from Step 0 above>",
  "APP_SECRET_KEY":     "<value from Step 0 above>"
}
```

```bash
# Verify stanza written correctly
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.MultiTaskWS/MultiTaskWS_config.json').read_text())
print(json.dumps(cfg.get('llcRentalTracker', 'MISSING'), indent=2))
"
```

**PA: Step 2 — Fix `~/.llcRentalTracker/config.json`**

Replace the entire file:

```json
{
  "default": ["WBGroupLLC", 2025],
  "llcList": [
    {
      "llcName":   "WBGroupLLC",
      "dataName":  "WBGroupLLC",
      "bus_repo":  "/home/wbgroup/llc/LLC-WBGroup",
      "books_dir": "books",
      "years":     [2025]
    }
  ],
  "secrets": {
    "APP_GPG_PASSPHRASE": "<PA canonical value>",
    "APP_SECRET_KEY":     "<PA canonical value>"
  }
}
```

Changes: removes duplicate stanza, fixes `llcName`, removes `master_passphrase`,
adds `secrets:` block, adopts nested `years:` schema (`llcRentalTracker #19`).

**Note — key name migration:** Gate 1 writes `APP_GPG_PASSPHRASE`/`APP_SECRET_KEY` because the
current code (`@a47da23`) reads those names. Gate 2 Step 8 (`wsCmd.py --setup` with Phase 2 code)
will rewrite the `secrets:` block to `APP_GPG_PASSPHRASE`/`APP_SECRET_KEY` automatically.

**PA: Step 3 — Clean `llcProfile_WBGroupLLC.json`** (PA = master, push from PA)

Remove `YEAR`, `TOP`, `dirAccounting`, `MultiTaskWS_Config` — keep only `entity` and `F1065`.

```bash
cd ~/llc/LLC-WBGroup

python3 -c "
import json
from pathlib import Path
p = Path('books/Accts/llcProfile_WBGroupLLC.json')
cfg = json.loads(p.read_text())
# Keep only entity and F1065
clean = {k: cfg[k] for k in ('entity', 'F1065') if k in cfg}
p.write_text(json.dumps(clean, indent=2))
print('Removed:', [k for k in cfg if k not in clean])
"

git add books/Accts/llcProfile_WBGroupLLC.json
git commit -m "refactor(profile): remove filesystem keys — entity/F1065 only"
git push
```

**PA: Step 4 — Remove `keys.json.gpg` from BUS repo** (if it exists)

```bash
cd ~/llc/LLC-WBGroup
if [ -f books/Accts/keys.json.gpg ]; then
  git rm books/Accts/keys.json.gpg
  git commit -m "chore: remove keys.json.gpg — replaced by platform stanza"
  git push
else
  echo "keys.json.gpg not present — nothing to remove"
fi
```

**PA: Step 5 — Reload and verify**

```bash
# PA dashboard → Web tab → Reload
# Then visit https://<pa-domain>/llcRentalTracker/login
# App should start; APP_GPG_PASSPHRASE loaded from ~/.llcRentalTracker/config.json secrets:
```

Expected startup log (PA error log):
```
startup: llc=WBGroupLLC year=2025 secret_key_src=tracker_config gpg_passphrase=set
```

---

#### Local: Gate 1 Steps (parallel with PA, no code needed)

**Local: Step 1 — Pull cleaned BUS repo**

```bash
cd /path/to/LLC-WBGroup
git pull
# Gets cleaned llcProfile_WBGroupLLC.json (no filesystem keys)
```

**Local: Step 2 — Fix `~/.llcRentalTracker/config.json`**

Replace the `llcList` entry and fix the passphrase typo (remove the extra space):

```json
{
  "default": ["WBGroupLLC", 2025],
  "llcList": [
    {
      "llcName":   "WBGroupLLC",
      "dataName":  "WBGroupLLC",
      "bus_repo":  "/Users/frankrojas/Library/CloudStorage/GoogleDrive-frankr6591@gmail.com/My Drive/Family/Assets/LLC-WBGroup",
      "books_dir": "books",
      "years":     [2025]
    }
  ],
  "secrets": {
    "APP_GPG_PASSPHRASE": "<PA canonical value — no trailing space>",
    "APP_SECRET_KEY":     "<generated locally by --setup>"
  }
}
```

**Note — key name migration:** Same as PA: Gate 1 uses current `LLC_` names (current code compatibility).
Gate 2 Step 8 (`wsCmd.py --setup` with Phase 2 code) rewrites to `APP_GPG_PASSPHRASE`/`APP_SECRET_KEY`.
```

**Local: Step 3 — Verify standalone start**

```bash
cd /path/to/llcRentalTracker
python3 wsCmd.py --start --llcName WBGroupLLC --year 2025 --port 5000 --load
# Reads APP_GPG_PASSPHRASE + APP_SECRET_KEY from ~/.llcRentalTracker/config.json secrets: (sole source, current code names)
```

---

#### Gate 2 — After Phase 2 Code (requires llcRentalTracker Phase 2 merge)

Once `llcRentalTracker` Phase 2a–2d is merged and pushed:

**PA: Step 6 — Pull Phase 2 code**

```bash
cd ~/pyTrackers/llcRentalTracker
git pull
```

**PA + Local: Step 7 — Rename platform config file**

```bash
# Rename file only — directory stays ~/.MultiTaskWS/
mv ~/.MultiTaskWS/MultiTaskWS_config.json ~/.MultiTaskWS/config.json
```

**PA: Step 8 — Run `wsCmd.py --setup` to verify and formalize**

```bash
cd ~/pyTrackers/llcRentalTracker
python3 wsCmd.py --setup --llcName WBGroupLLC
# With Phase 2 code:
# → reads APP_GPG_PASSPHRASE from config.json secrets: (Gate 1 value)
# → renames secrets: keys LLC_ → APP_  (APP_GPG_PASSPHRASE / APP_SECRET_KEY)
# → writes llcRentalTracker stanza to ~/.MultiTaskWS/config.json (formalizes it)
# → verifies pw.json.gpg decrypts correctly with APP_GPG_PASSPHRASE
# → prints "✓ Configuration verified"
```

**PA: Step 9 — Final reload and smoke test**

```bash
# PA dashboard → Web tab → Reload
```

Expected startup log after Phase 2:
```
startup: llc=WBGroupLLC year=2025 secret_key_src=tracker_config gpg_passphrase=set
```
(`~/.llcRentalTracker/config.json` `secrets:` — sole authority, no tiers, no fallback)

---

#### Target State Verification Checklist

After all steps complete, verify on PA:

```bash
# 1. Platform config in correct location
ls ~/.MultiTaskWS/config.json                                       # ✓ exists

# 2. llcRentalTracker stanza present
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.MultiTaskWS/config.json').read_text())
rt = cfg.get('llcRentalTracker', {})
print('APP_GPG_PASSPHRASE:', 'SET' if rt.get('APP_GPG_PASSPHRASE') else 'MISSING')
print('APP_SECRET_KEY    :', 'SET' if rt.get('APP_SECRET_KEY') else 'MISSING')
"

# 3. llcRentalTracker config clean
python3 -c "
import json; from pathlib import Path
cfg = json.loads((Path.home()/'.llcRentalTracker/config.json').read_text())
print('llcList count  :', len(cfg.get('llcList', [])))   # should be 1
print('master_pp      :', 'PRESENT — REMOVE' if 'master_passphrase' in cfg else 'absent ✓')
s = cfg.get('secrets', {})
print('APP_GPG_PP     :', 'SET' if s.get('APP_GPG_PASSPHRASE') else 'MISSING')
print('APP_SECRET_KEY :', 'SET' if s.get('APP_SECRET_KEY') else 'MISSING')
print('LLC_ keys      :', 'STALE — run --setup to migrate' if s.get('APP_GPG_PASSPHRASE') else 'absent ✓')
stanza = cfg['llcList'][0]
print('llcName        :', stanza.get('llcName'))          # WBGroupLLC
print('years          :', stanza.get('years'))            # [2025]
"

# 4. Profile is clean
python3 -c "
import json; from pathlib import Path
p = Path('/home/wbgroup/llc/LLC-WBGroup/books/Accts/llcProfile_WBGroupLLC.json')
cfg = json.loads(p.read_text())
bad = [k for k in ('YEAR','TOP','dirAccounting','MultiTaskWS_Config') if k in cfg]
print('Filesystem keys still present:', bad or 'none ✓')
"

# 5. keys.json.gpg removed
ls ~/llc/LLC-WBGroup/books/Accts/keys.json.gpg 2>/dev/null \
  && echo "PRESENT — REMOVE" || echo "absent ✓"

# 6. pw.json.gpg decrypts  (source: ~/.llcRentalTracker/config.json secrets: — sole authority)
LLC_PP=$(python3 -c "
import json; from pathlib import Path
print(json.loads((Path.home()/'.llcRentalTracker/config.json').read_text())['secrets']['APP_GPG_PASSPHRASE'])
")
gpg --batch --decrypt --passphrase "$LLC_PP" \
    ~/llc/LLC-WBGroup/books/Accts/pw.json.gpg 2>/dev/null \
  && echo "pw.json.gpg decrypts ✓" || echo "DECRYPT FAILED"
```
 
| File | Change |
|---|---|
| `pyMultiTaskWS` codebase | Rename `MultiTaskWS_config.json` → `config.json` (file only; `~/.MultiTaskWS/` directory unchanged) |
| `pyMultiTaskWS/docs/design_trackerApp.md` | Update §3.5 per-BUS deployment clause |
| `llcRentalTracker/wsgi.py` | Replace three-tier `_inject_secrets()` with single-source `APP_` → `LLC_` env var injection; hard `RuntimeError` if missing |
| `llcRentalTracker/wsCmd.py` | `provision_new_bus`: prompt `APP_GPG_PASSPHRASE`, remove keys.json.gpg; `setup`: read `APP_`, generate `APP_SECRET_KEY`; `addTracker`: write tracker env var names to platform stanza; `_inject_env_from_profile`: remove fallback chain, read `APP_` keys, hard fail |
| `llcRentalTracker/ledger/setup_paths.py` | Keep `SECRETS` global + `write_secrets()`; update nested schema in `find_stanza()` (llcRentalTracker #19) |
| `llcRentalTracker/docs/design_LLC_01.3-login_auth.md` | Rewrite startup sequence; remove keys.json.gpg / master_passphrase; update config schema to `APP_GPG_PASSPHRASE` / `APP_SECRET_KEY` (Design 3) |
| `LLC-WBGroup/books/Accts/` | Remove `keys.json.gpg` only — `pw.json.gpg` stays |
| `~/.llcRentalTracker/config.json` | Remove `master_passphrase`; fix duplicate stanza; migrate to nested schema |
| `~/.MultiTaskWS/config.json` | Add `llcRentalTracker: { APP_GPG_PASSPHRASE, APP_SECRET_KEY }` stanza |
| `~/.adminTracker/config.json` | Create (convention; initially empty) |

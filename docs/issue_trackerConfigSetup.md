# Tracker Config & Secrets Setup — Architecture Assessment & Action Plan

## Context

Full multi-layer architecture assessment covering `pyMultiTaskWS`, `llcRentalTracker`, and
`LLC-WBGroup` (BUS) data repo. Phase 1 (startup crash fix) is already merged in
`llcRentalTracker@a47da23`. This document tracks Phases 2–3.

**Guiding Principles**
- Consistent and elegant above all
- `adminTracker` and `llcRentalTracker` follow the same config/setup pattern
- `adminTracker` gets its own `~/.adminTracker/config.json`
- Platform config renamed to `~/.MultiTask/config.json`
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
- Has `rentalTracker` in `Trackers` list but **no `rentalTracker` credentials stanza** ✗
- `WEB_GPG_PASSPHRASE` at top level is the platform-wide passphrase (not tracker-specific)

---

## Bugs

### Bug 1 — `rentalTracker` credentials stanza MISSING from platform config

Per `design_trackerApp.md §3.2`, `wsCmd.py --setup` must write a tracker stanza to the
platform config so the platform can inject the tracker's secrets as env vars:

```json
"rentalTracker": {
  "LLC_GPG_PASSPHRASE": "...",
  "LLC_SECRET_KEY": "..."
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
contract. It was invented to distribute `LLC_GPG_PASSPHRASE` and `LLC_SECRET_KEY` across
hosts because the `rentalTracker` platform stanza (Bug 1) was never written. Once Bug 1
is fixed, the platform stanza is the canonical source for these secrets and `keys.json.gpg`
is redundant.

**Remove `keys.json.gpg` from the BUS repo.** The `master_passphrase` (which only existed
to decrypt it) is also removed.

### Design 3 — Per-tracker unique passphrase and SECRET_KEY

**Each tracker requires its own unique `GPG_PASSPHRASE` and `SECRET_KEY`.** Two reasons:

1. **GPG passphrase** — each tracker encrypts its own `pw.json.gpg`. A shared passphrase
   means a compromised tracker exposes all others' user databases. The existing
   `adminTracker` pattern proves this is intentional: `APP_GPG_PASSPHRASE` for adminTracker
   is deliberately different from `LLC_GPG_PASSPHRASE` for rentalTracker.

2. **Flask `SECRET_KEY`** — signs session cookies. Shared keys make a session token from
   one tracker cryptographically valid in another — a direct security vulnerability.

The `secrets` block in `~/.llcRentalTracker/config.json` is therefore **correct** — it
holds the tracker's own unique secrets. It serves as the **standalone-mode equivalent**
of the `rentalTracker` platform stanza:

| Mode | Secret source |
|---|---|
| Running under MultiTaskWS | `~/.MultiTask/config.json` → `rentalTracker:` stanza, injected as env vars |
| Standalone (`wsCmd.py --start`) | `~/.llcRentalTracker/config.json` → `secrets:` block |

Same values, two access paths. The `secrets:` block is not a flaw — it must exist for
standalone mode. Only `master_passphrase` is removed (it belonged to `keys.json.gpg`,
which is going away).

#### Passphrase & SECRET_KEY setup and management workflow

**Initial setup (`wsCmd.py --setup` on any host)**
1. Generate `LLC_GPG_PASSPHRASE` + `LLC_SECRET_KEY` (or prompt operator)
2. Write `rentalTracker: { LLC_GPG_PASSPHRASE, LLC_SECRET_KEY }` to `~/.MultiTask/config.json`
3. Write the same values to `~/.llcRentalTracker/config.json` `secrets:` block
4. Create `pw.json.gpg` in BUS repo encrypted with `LLC_GPG_PASSPHRASE`; push from PA

**Runtime injection priority (wsgi.py / wsCmd.py --start)**
```
Tier 1: os.environ already set (operator / PA env tab)          ← highest
Tier 2: ~/.MultiTask/config.json  rentalTracker: stanza         ← platform mode
Tier 3: ~/.llcRentalTracker/config.json  secrets: block         ← standalone mode
```

**Key rotation**
1. Regenerate `LLC_GPG_PASSPHRASE` + `LLC_SECRET_KEY`
2. Re-encrypt `pw.json.gpg` with new passphrase; push from PA (master host)
3. Update both `~/.MultiTask/config.json` and `~/.llcRentalTracker/config.json` on all hosts
4. git pull on all hosts + reload app

**Adding a second host (local dev or new PA account)**
1. Clone both repos
2. Run `wsCmd.py --setup` — writes stanza + secrets block with the shared passphrase
3. `git pull` on BUS repo → gets PA's `pw.json.gpg` (same users, same passphrase)

### Design Flaw 4 — Naming inconsistency across layers

| What | Where | Name |
|---|---|---|
| GPG passphrase (platform-wide) | `~/.MultiTask/config.json` | `WEB_GPG_PASSPHRASE` |
| GPG passphrase (rentalTracker) | env var + stanza | `LLC_GPG_PASSPHRASE` |
| GPG passphrase (adminTracker) | `~/.MultiTask/config.json` adminTracker stanza | `APP_GPG_PASSPHRASE` |
| Flask secret (platform) | `~/.MultiTask/config.json` | `WEB_SECRET_KEY` |
| Flask secret (rentalTracker) | env var + stanza | `LLC_SECRET_KEY` |
| Flask secret (adminTracker stanza) | `~/.MultiTask/config.json` | `WEB_SECRET_KEY` |

Per `design_trackerApp.md §3.2`, the convention is `<TRACKER>_GPG_PASSPHRASE` /
`<TRACKER>_SECRET_KEY` where `<TRACKER>` matches the tracker slug (§3.6: short lowercase).
Recommendation: formalize `llc` as the rentalTracker slug → `LLC_GPG_PASSPHRASE` and
`LLC_SECRET_KEY` are then correctly formed and consistent.

### Design Flaw 5 — Platform config path naming

- Current: `~/.MultiTaskWS/MultiTaskWS_config.json`
- Required: `~/.MultiTask/config.json`

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
~/.MultiTask/config.json                       ← RENAMED from ~/.MultiTaskWS/MultiTaskWS_config.json
  WEB_SECRET_KEY                               platform Flask signing key
  Trackers: [...]                              registered tracker list
  adminTracker: {                              built-in tracker stanza
    APP_GPG_PASSPHRASE: "..._adminTracker",
    WEB_SECRET_KEY: "..."
  }
  rentalTracker: {                             external tracker stanza (CURRENTLY MISSING — Bug 1)
    LLC_GPG_PASSPHRASE: "...",
    LLC_SECRET_KEY: "..."
  }

~/.adminTracker/config.json                    ← NEW (consistency with per-tracker config pattern)

~/.llcRentalTracker/config.json                ← CLEANED
  default, llcList (nested M BUS × N years)    keep — see llcRentalTracker #19
  secrets: { LLC_GPG_PASSPHRASE, LLC_SECRET_KEY }  keep — standalone-mode fallback
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
- Rename `~/.MultiTaskWS/` → `~/.MultiTask/`; `MultiTaskWS_config.json` → `config.json`
- Update all references in `pyMultiTaskWS`, `llcRentalTracker`, `adminTracker`
- Update `wsgi.py _inject_secrets()` Tier 3 path

**2b — Write `rentalTracker` stanza in `wsCmd.py --setup`** (`llcRentalTracker`)
- `wsCmd.py --setup` writes `rentalTracker: { LLC_GPG_PASSPHRASE, LLC_SECRET_KEY }` to `~/.MultiTask/config.json`
- `wsCmd.py --setup` writes same values to `~/.llcRentalTracker/config.json` `secrets:` block (standalone fallback)
- Remove code that writes secrets to `llcProfile_*.json`
- Remove `write_secrets()` from `setup_paths.py`; remove `SECRETS` global

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
Replace multi-tier fallback with the documented three-tier priority chain:
```python
# Tier 1: os.environ (already set by operator / PA env tab) — setdefault handles this
# Tier 2: ~/.MultiTask/config.json  rentalTracker: stanza
stanza = load_tracker_stanza("rentalTracker")   # from pyMultiTaskWS platform lib
os.environ.setdefault("LLC_GPG_PASSPHRASE", stanza.get("LLC_GPG_PASSPHRASE", ""))
os.environ.setdefault("LLC_SECRET_KEY",     stanza.get("LLC_SECRET_KEY", ""))
# Tier 3: ~/.llcRentalTracker/config.json  secrets: block  (standalone fallback)
_s = _sp.SECRETS or {}
os.environ.setdefault("LLC_GPG_PASSPHRASE", _s.get("LLC_GPG_PASSPHRASE", ""))
os.environ.setdefault("LLC_SECRET_KEY",     _s.get("LLC_SECRET_KEY", ""))
```

**3b — `wsCmd.py --start` standalone** (`llcRentalTracker`)
Same three-tier chain; reads from `~/.llcRentalTracker/config.json` `secrets:` as
primary source in standalone mode (Tier 2 / Tier 3 order reversed when no platform).

**3c — Reconfigure PA**
1. `git pull` both repos
2. Run `wsCmd.py --setup` with updated code → writes `rentalTracker` stanza + `secrets:`
3. Reload PA web app

---

## Files Affected

| File | Change |
|---|---|
| `pyMultiTaskWS` codebase | Rename `~/.MultiTaskWS/` → `~/.MultiTask/`; `MultiTaskWS_config.json` → `config.json` |
| `pyMultiTaskWS/docs/design_trackerApp.md` | Update §3.5 per-BUS deployment clause |
| `llcRentalTracker/wsgi.py` | Implement documented three-tier secret injection |
| `llcRentalTracker/wsCmd.py` | Write `rentalTracker` stanza + `secrets:`; remove `keys.json.gpg` flow |
| `llcRentalTracker/ledger/setup_paths.py` | Remove `SECRETS` global; remove `write_secrets()`; nested schema in `find_stanza()` |
| `llcRentalTracker/docs/design_LLC_01.3-login_auth.md` | Rewrite startup sequence; remove keys.json.gpg |
| `LLC-WBGroup/books/Accts/` | Remove `keys.json.gpg` only — `pw.json.gpg` stays |
| `~/.llcRentalTracker/config.json` | Remove `master_passphrase`; fix duplicate stanza; migrate to nested schema |
| `~/.MultiTask/config.json` | Add `rentalTracker: { LLC_GPG_PASSPHRASE, LLC_SECRET_KEY }` stanza |
| `~/.adminTracker/config.json` | Create (convention; initially empty) |

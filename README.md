# pyMultiTaskWS — MultiTrack Web Platform

Core platform services for hosting multiple independent Flask apps
(**Trackers**) under a single PythonAnywhere web server using Werkzeug's
`DispatcherMiddleware`.

## What's in this package

| Module | Purpose |
|--------|---------|
| `multitrack_wsgi.py` | Dispatcher template — copy to `~/multitrack_wsgi.py` on PA |
| `multitrack/auth.py` | Shared auth: GPG-encrypted user DB, `/login` `/logout` `/register` routes, `login_required` decorator |
| `multitrack/templates/` | Generic `login.html` and `register.html` (Tracker may override) |
| `setup/setupWebServerCmd.py` | Interactive one-shot PA setup per Tracker |
| `setup/init_userdb.py` | CLI seed tool for a Tracker user DB |
| `docs/design_webserver.md` | Full architecture and PA deployment guide |

## Quick start

### 1. Add `multitrack` to your Tracker's sys.path

```python
# In the Tracker's wsgi.py or app factory:
import sys
sys.path.insert(0, '/path/to/pyMultiTaskWS')
from multitrack.auth import make_auth_routes
```

### 2. Wire auth into your Flask app

```python
import os, secrets
from pathlib import Path
from multitrack.auth import make_auth_routes

self.app.secret_key = os.environ.get("MYTRACKER_SECRET_KEY", secrets.token_hex(32))
make_auth_routes(
    self.app,
    db_path=Path("/path/to/Accts/pw.json.gpg"),
    tracker_name="My Tracker",
)
```

This registers `/login`, `/logout`, `/register` and protects all other
routes via a `before_request` guard.

### 3. Run PA setup

```bash
python3.10 setup/setupWebServerCmd.py \
    --tracker-name "My Tracker" \
    --tracker-id   mytracker \
    --db           ~/mytracker/repo/Accts/pw.json.gpg \
    --notebooks    ~/mytracker/repo/path/to/notebooks \
    --seed-user    admin \
    --seed-pass    "Admin0Pass!"
```

Copy the printed block into `~/multitrack_wsgi.py`, then reload the PA
Web tab.

## Auth module API

```python
from multitrack.auth import (
    make_auth_routes,   # register /login /logout /register + before_request guard
    login_required,     # decorator for per-route protection
    load_users,         # decrypt + parse pw.json.gpg → list[dict]
    save_users,         # serialize + encrypt atomically
    find_user,          # case-insensitive username lookup
    hash_password,      # SHA-256 hex
    get_passphrase,     # read MULTITRACK_GPG_PASSPHRASE env var
    gpg_decrypt,        # decrypt file → bytes (passphrase via os.pipe)
    gpg_encrypt,        # encrypt bytes → file atomically
    ALLOWED_ROLES,      # default role list
)
```

## Template variables

`login.html` and `register.html` expect:

| Variable | Source |
|----------|--------|
| `tracker_name` | `make_auth_routes(tracker_name=...)` |
| `roles` | `make_auth_routes(allowed_roles=...)` or `ALLOWED_ROLES` |
| `errors` | dict of field-level validation errors (register only) |
| `form` | dict of previously submitted form values (register only) |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `MULTITRACK_GPG_PASSPHRASE` | GPG symmetric passphrase for the user DB |
| `<TRACKERID>_GPG_PASSPHRASE` | Per-Tracker override (set in `multitrack_wsgi.py`) |

See `docs/design_webserver.md` for the full architecture guide.

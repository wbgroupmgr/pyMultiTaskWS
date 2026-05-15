#!/usr/bin/env python3
"""
init_userdb.py — seed a Tracker's user DB with one default account.

Usage:
    python init_userdb.py --db /path/to/Accts/pw.json.gpg \
                          --username myuser \
                          --password MyPass1! \
                          --role member \
                          --full-name "My Name" \
                          [--force]

The GPG passphrase must be set in MULTITRACK_GPG_PASSPHRASE before running.
--force overwrites the DB if it already exists.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow running from anywhere — add project root to sys.path
_here = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_here))

from multitrack.auth import find_user, hash_password, load_users, save_users


def main():
    ap = argparse.ArgumentParser(description="Seed a Tracker user DB")
    ap.add_argument("--db",        required=True, help="Path to pw.json.gpg")
    ap.add_argument("--username",  required=True)
    ap.add_argument("--password",  required=True)
    ap.add_argument("--role",      default="member")
    ap.add_argument("--full-name", default="")
    ap.add_argument("--phone",     default="")
    ap.add_argument("--force",     action="store_true",
                    help="Overwrite existing DB rather than appending")
    args = ap.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    users = []
    if db_path.exists() and not args.force:
        try:
            users = load_users(db_path)
            print(f"  Existing DB found ({len(users)} user(s)).")
        except RuntimeError as exc:
            print(f"  Could not read existing DB: {exc}")
            sys.exit(1)

    if find_user(users, args.username):
        if args.force:
            users = [u for u in users if u.get("username", "").lower() != args.username.lower()]
            print(f"  Removed existing '{args.username}' (--force).")
        else:
            print(f"  User '{args.username}' already exists. Use --force to overwrite.")
            sys.exit(1)

    users.append({
        "username":   args.username,
        "password":   hash_password(args.password),
        "full_name":  args.full_name,
        "phone":      args.phone,
        "role":       args.role,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    })

    try:
        save_users(db_path, users)
    except RuntimeError as exc:
        print(f"  Save failed: {exc}")
        sys.exit(1)

    print(f"  + Seeded '{args.username}' (role={args.role}) → {db_path}")


if __name__ == "__main__":
    main()

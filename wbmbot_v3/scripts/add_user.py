#!/usr/bin/env python3

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from utility.config_store import FirestoreConfigStore  # noqa: E402


def _resolve_user_id(config: dict, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    env_user = os.getenv("WBM_USER_ID")
    if env_user:
        return env_user
    if config.get("user_id"):
        return config.get("user_id")
    notifications = (config.get("notifications_email") or "").strip()
    if notifications:
        return notifications
    emails = config.get("emails") or []
    if emails:
        return str(emails[0]).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a WBM config JSON to Firestore."
    )
    parser.add_argument(
        "path",
        help="Path to a wbm_config.json file.",
    )
    parser.add_argument(
        "--user-id",
        dest="user_id",
        default=None,
        help="Firestore document key for this user (or set WBM_USER_ID).",
    )
    parser.add_argument(
        "--project-id",
        dest="project_id",
        default=None,
        help="Firestore project ID (or set FIRESTORE_PROJECT_ID).",
    )
    parser.add_argument(
        "--collection",
        dest="collection",
        default=None,
        help="Firestore collection for configs (or set FIRESTORE_CONFIG_COLLECTION).",
    )
    parser.add_argument(
        "--database",
        dest="database",
        default=None,
        help="Firestore database ID (or set FIRESTORE_DATABASE).",
    )
    parser.add_argument(
        "--credentials",
        dest="credentials",
        default=None,
        help="Path to service account JSON (or set GOOGLE_APPLICATION_CREDENTIALS).",
    )

    args = parser.parse_args()

    with open(args.path, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    user_id = _resolve_user_id(config, args.user_id)
    if not user_id:
        print(
            "Unable to resolve a user id. Provide --user-id or set WBM_USER_ID.",
            file=sys.stderr,
        )
        return 2

    store = FirestoreConfigStore(
        project_id=args.project_id or os.getenv("FIRESTORE_PROJECT_ID"),
        collection=args.collection or os.getenv("FIRESTORE_CONFIG_COLLECTION"),
        credentials_path=args.credentials
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        database=args.database or os.getenv("FIRESTORE_DATABASE"),
    )
    store.initialize()
    store.save_config(user_id, config)
    print(f"Uploaded config to Firestore as '{user_id}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

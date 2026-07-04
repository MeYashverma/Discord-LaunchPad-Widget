"""Inspect the current widget identity fields from Discord.

Usage:
    DISCORD_APPLICATION_ID=... DISCORD_USER_ID=... DISCORD_BOT_TOKEN=... \\
        python scripts/inspect_widget.py

Prints the JSON Discord has stored for your widget, so you can see
exactly what field names the editor created.
"""

from __future__ import annotations

import json
import os
import sys

import requests


def main() -> int:
    app_id = os.environ.get("DISCORD_APPLICATION_ID", "")
    user_id = os.environ.get("DISCORD_USER_ID", "")
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not (app_id and user_id and token):
        print(
            "Set DISCORD_APPLICATION_ID, DISCORD_USER_ID, DISCORD_BOT_TOKEN",
            file=sys.stderr,
        )
        return 2

    url = (
        f"https://discord.com/api/v9/applications/{app_id}"
        f"/users/{user_id}/identities/0/profile"
    )
    headers = {"Authorization": f"Bot {token}"}
    resp = requests.get(url, headers=headers, timeout=20)
    print(f"HTTP {resp.status_code}")
    try:
        data = resp.json()
        print(json.dumps(data, indent=2))
    except ValueError:
        print(resp.text[:500])
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())

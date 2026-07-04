"""Upload a local image to a Discord channel and print the resulting URL.

Why this exists:
    Discord's profile widget image fields expect an https URL pointing to a
    file already on Discord's CDN (``cdn.discordapp.com``). The cleanest way
    to get one for free is to upload the file as an attachment to a channel
    the bot can read, then read back the resulting ``attachments[].url``.

Usage:
    DISCORD_BOT_TOKEN=... DISCORD_TARGET_CHANNEL_ID=... \\
        python scripts/upload_image.py path/to/image.png

The script prints the URL to stdout so it can be captured by the GitHub
Action that wraps it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests


def upload(token: str, channel_id: str, image_path: Path) -> str:
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}"}
    with image_path.open("rb") as f:
        files = {"files[0]": (image_path.name, f, "application/octet-stream")}
        resp = requests.post(url, headers=headers, files=files, timeout=30)
    if not (200 <= resp.status_code < 300):
        raise SystemExit(f"Upload failed: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    attachments = data.get("attachments") or []
    if not attachments:
        raise SystemExit(f"No attachments in response: {data}")
    return attachments[0]["url"]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: upload_image.py PATH", file=sys.stderr)
        return 2
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel_id = os.environ.get("DISCORD_TARGET_CHANNEL_ID", "")
    if not token or not channel_id:
        print("DISCORD_BOT_TOKEN and DISCORD_TARGET_CHANNEL_ID must be set", file=sys.stderr)
        return 2
    image_path = Path(sys.argv[1])
    if not image_path.is_file():
        print(f"image not found: {image_path}", file=sys.stderr)
        return 2
    url = upload(token, channel_id, image_path)
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

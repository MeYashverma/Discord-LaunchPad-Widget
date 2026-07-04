"""One-shot helper: print the JSON payload the widget would PATCH.

Useful for debugging what would be sent without actually hitting Discord.

Usage:
    python scripts/inspect_payload.py [--dry-run]
"""

from __future__ import annotations

import json
import sys

from launchpad_widget.config import AppConfig
from launchpad_widget.services.orchestrator import build_default_orchestrator
from launchpad_widget.utils.logging_setup import configure_logging


def main() -> int:
    config = AppConfig.load()
    configure_logging(config.log_file, level=config.log_level)
    config.dry_run = True  # never PATCH

    orchestrator = build_default_orchestrator(config)
    launch = orchestrator._fetch_next_launch()
    if launch is None:
        print(json.dumps({"error": "no upcoming launch found"}), file=sys.stderr)
        return 1

    image_info = orchestrator.image_service.best_image_for(launch)
    payload = orchestrator.payload_builder.build(launch, image_info=image_info)
    print(json.dumps({
        "mission": launch.mission_name,
        "rocket": launch.rocket_name,
        "provider": launch.launch_provider,
        "window": launch.launch_timestamp_utc,
        "image_source": (image_info or {}).get("source"),
        "image_path": (image_info or {}).get("local_path"),
        "payload": payload,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

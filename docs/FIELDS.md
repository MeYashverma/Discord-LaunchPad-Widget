# Widget Fields Reference

This is the authoritative list of field names produced by the daemon.
Each name is the value of the `name` key in the identities payload and
must match a Data Field in your Discord widget editor **exactly**.

## Text fields (type 1)

| Name      | Source                                     | Notes |
| --------- | ------------------------------------------ | ----- |
| `mission` | `Launch.mission_name`                      | Truncated to 80 chars |
| `rocket`  | `Launch.rocket_full_name` (falls back to `rocket_name`) | Truncated to 80 chars |
| `provider`| `Launch.launch_provider`                   | Truncated to 60 chars |
| `status`  | derived: `failreason` → "Scrubbed", `hold_reason` → "Hold: …", else `Launch.launch_status` | Truncated to 50 chars |
| `countdown`| derived: `T-<days>d HH:MM:SS`              | Updates every cycle |
| `window`  | `Launch.extra.window_start` / `window_end` | "2026-07-08 14:30 UTC → 18:30 UTC" |
| `site`    | `Launch.launch_pad` (falls back to `launch_site`) | Truncated to 60 chars |
| `location`| `Launch.launch_location`                   | Truncated to 60 chars |
| `country` | `Launch.country`                           | Truncated to 30 chars |
| `orbit`   | `Launch.orbit` (falls back to `destination`) | "—" when unknown |
| `crew`    | `Launch.crew_summary()` (4 names + " +N" tail) | "Uncrewed" if empty |
| `type`    | `Launch.mission_type`                      | "—" when unknown |

## Numeric fields (type 2)

| Name                | Source                                    | Notes |
| ------------------- | ----------------------------------------- | ----- |
| `probability`       | `Launch.launch_probability`               | `0` if not reported |
| `seconds_to_launch` | derived: max((NET - now).total_seconds, 0) | Always non-negative |

## Image field (type 1, value is a URL)

| Name   | Source                                                     |
| ------ | ---------------------------------------------------------- |
| `image`| `ImageService.best_image_for(launch)["local_path"]` rendered as a URL — see image priority below |

## Image priority

`ImageService.priority` (configurable via `image_priority` in
`config.json` / `IMAGE_PRIORITY` env var). The default order matches the
spec:

1. `rocket` — rocket artwork from the API (e.g. Falcon 9 photo)
2. `mission_patch` — mission insignia
3. `launch_artwork` — official launch poster / hero image
4. `launchpad` — pad image (rarely available)

If none resolve, the bundled `launchpad_widget/assets/fallback.png` is
used so the widget never shows an empty image slot.

## Why so many fields?

The widget editor lets you bind any subset of these to display slots;
the daemon sends them all and Discord silently drops the rest. This
means you can re-arrange your widget layout at any time without touching
the code — just edit the Discord side.

# Widget Fields Reference

This is the authoritative list of field names the daemon sends to
Discord. Each name is the value of the `name` key in the identities
payload and must match a Data Field in your Discord widget editor
**exactly** (case-sensitive, including spaces and capitalisation).

## Widget Top (5 fields)

These appear in the "Top" section of the widget editor (the larger
image + text area at the top of the rendered widget).

| Order | Name | Type | Source | Example |
| ----- | ---- | ---- | ------ | ------- |
| 1 | `Image` | image | `ImageService` (best of rocket / patch / artwork / fallback) | `https://cdn.discordapp.com/...` |
| 2 | `Title` | text | `Launch.mission_name` | `Falcon 9 Block 5 \| Starlink Group 10-50` |
| 3 | `Subtitle 1` | text | `rocket + provider` | `Falcon 9 Block 5 · SpaceX` |
| 4 | `Subtitle 2` | text | `countdown` | `T-13:54:32` |
| 5 | `Subtitle 3` | text | `site + location` | `Cape Canaveral SFS, FL, USA` |

## Widget Bottom (14 fields)

These appear in the "Bottom" section (the stat list below the image).

| Order | Name | Type | Source | Notes |
| ----- | ---- | ---- | ------ | ----- |
| 1 | `mission` | text | `Launch.mission_name` | Truncated to 80 chars |
| 2 | `rocket` | text | `Launch.rocket_full_name` | Falls back to `rocket_name` |
| 3 | `provider` | text | `Launch.launch_provider` | Truncated to 60 chars |
| 4 | `status` | text | derived | `Go`, `Hold: …`, `Scrubbed`, `Scheduled` |
| 5 | `countdown` | text | derived | `T-Dd HH:MM:SS` or `T-HH:MM:SS` |
| 6 | `window` | text | `Launch.extra.window_start/end` | `2026-07-05 10:36 UTC → 14:36 UTC` |
| 7 | `site` | text | `Launch.launch_pad` (or `launch_site`) | Truncated to 60 chars |
| 8 | `location` | text | `Launch.launch_location` | Truncated to 60 chars |
| 9 | `country` | text | `Launch.country` | Truncated to 30 chars |
| 10 | `orbit` | text | `Launch.orbit` (or `destination`) | `Low Earth Orbit` |
| 11 | `crew` | text | `Launch.crew` summary | `J. Smith, A. Patel +2` or `Uncrewed` |
| 12 | `type` | text | `Launch.mission_type` | `Communications` / `Human Spaceflight` |
| 13 | `probability` | number | `Launch.launch_probability` | `85` (0 if not reported) |
| 14 | `image` | image | same URL as `Image` (top) | `https://cdn.discordapp.com/...` |

## Type codes (Discord dynamic-identity)

| Code | Meaning | `value` shape |
| ---- | ------- | ------------- |
| `1` | Text | `"any string"` |
| `2` | Number | `42` (integer or float) |
| `3` | Image | `{"url": "https://..."}` |

The daemon always uses the correct type for each field.

## Complete payload example

```json
{
  "username": "LaunchPad",
  "data": {
    "dynamic": [
      {"name": "Image",       "type": 3, "value": {"url": "https://cdn.discordapp.com/.../img.png"}},
      {"name": "Title",       "type": 1, "value": "Falcon 9 Block 5 | Starlink Group 10-50"},
      {"name": "Subtitle 1",  "type": 1, "value": "Falcon 9 Block 5 · SpaceX"},
      {"name": "Subtitle 2",  "type": 1, "value": "T-13:54:32"},
      {"name": "Subtitle 3",  "type": 1, "value": "Cape Canaveral SFS, FL, USA"},

      {"name": "mission",     "type": 1, "value": "Falcon 9 Block 5 | Starlink Group 10-50"},
      {"name": "rocket",      "type": 1, "value": "Falcon 9 Block 5"},
      {"name": "provider",    "type": 1, "value": "SpaceX"},
      {"name": "status",      "type": 1, "value": "Go for Launch"},
      {"name": "countdown",   "type": 1, "value": "T-13:54:32"},
      {"name": "window",      "type": 1, "value": "2026-07-05 10:36 UTC → 14:36 UTC"},
      {"name": "site",        "type": 1, "value": "Space Launch Complex 40"},
      {"name": "location",    "type": 1, "value": "Cape Canaveral SFS, FL, USA"},
      {"name": "country",     "type": 1, "value": "United States of America"},
      {"name": "orbit",       "type": 1, "value": "Low Earth Orbit"},
      {"name": "crew",        "type": 1, "value": "Uncrewed"},
      {"name": "type",        "type": 1, "value": "Communications"},
      {"name": "probability", "type": 2, "value": 0},
      {"name": "image",       "type": 3, "value": {"url": "https://cdn.discordapp.com/.../img.png"}}
    ]
  }
}
```

## Image field behaviour

- The `Image` field in Widget Top and the `image` field in Widget Bottom
  point to the **same** image URL.
- If no image is available and `DISCORD_TARGET_CHANNEL_ID` is unset,
  both fields receive `value: {"url": ""}` and Discord will not bind
  the image slot (it shows the default empty frame).
- If D.W.I.F processing fails, the raw launch image is used instead.

## Why case-sensitive names matter

Discord binds fields to widget editor slots by **exact name match**.
If your editor has `Mission` (capital M) but the daemon sends `mission`
(lowercase), the data won't bind to that slot. Always copy the names
**exactly** as shown in the tables above.

# Hosting — Running the Widget as a GitHub Actions Daemon

The repository is designed to run unattended on a GitHub-hosted runner.
The daemon loops inside a single workflow run, self-dispatching the next
run before exiting so the widget never goes stale.

## How the self-dispatch loop works

1. The workflow starts. The daemon runs `widget.py` in a loop.
2. Each cycle it fetches the next launch, picks an image, builds a
   payload, and PATCHes Discord.
3. When the daemon's soft runtime budget (`MAX_RUNTIME_SECONDS`, default
   5h50m) is exhausted, it `return`s on its own terms.
4. The workflow's last step POSTs to
   `/repos/{owner}/{repo}/actions/workflows/update.yml/dispatches` to
   queue the next run.
5. The next run starts within seconds, repeating the loop.

GitHub-hosted runners have a hard 6h ceiling. The 5h50m inner budget
guarantees the daemon exits cleanly *before* the runner SIGKILLs it
mid-request. The schedule fallback (`cron: "0 */6 * * *"`) catches the
edge case where the self-dispatch step itself fails.

## Why the workflow needs `actions: write`

Self-dispatching is a write operation against the GitHub Actions API.
`GITHUB_TOKEN` defaults to read-only, so the workflow explicitly requests
`actions: write` in its `permissions:` block. Without it, the
self-dispatch step silently returns 403 — the workflow would still be
green but no follow-up run would be queued.

## Concurrency

```
concurrency:
  group: launchpad-widget-daemon
  cancel-in-progress: false
```

Only one live updater is allowed at a time. If a second trigger (e.g. a
cron firing while the self-dispatched run is still up) tries to start,
it **queues** rather than killing the live daemon — `cancel-in-progress:
false` is intentional because the live daemon is making progress that
shouldn't be interrupted.

## Overriding tunables without touching the repo

Use **Settings → Secrets and variables → Actions → Variables** (not
Secrets) for non-sensitive overrides. The workflow forwards them as env
vars to the daemon.

| Variable                      | Default | Notes                              |
| ----------------------------- | ------- | ---------------------------------- |
| `PREFERRED_SOURCE`            | `launch_library` | `launch_library` or `spacex` |
| `UPDATE_INTERVAL_SECONDS`     | `300`   | Lower → fresher widget, more API calls |
| `MIN_PATCH_INTERVAL_SECONDS`  | `60`    | Don't drop below 30s (Discord 429) |
| `MAX_RUNTIME_SECONDS`         | `21000` | Keep below 21500s                  |
| `CACHE_TTL_SECONDS`           | `120`   | Higher → fewer upstream calls      |
| `DRY_RUN`                     | *(unset)* | Set to `true` to log-only         |
| `LOG_LEVEL`                   | `INFO`  | `DEBUG` is verbose but useful      |

## Local testing

```bash
# Set the same env vars the workflow sets
export DISCORD_APPLICATION_ID=...
export DISCORD_USER_ID=...
export DISCORD_BOT_TOKEN=...
export DRY_RUN=true     # important — don't PATCH while testing
export MAX_RUNTIME_SECONDS=120
python widget.py
```

The daemon will run for 2 minutes, log the JSON it would have sent, and
exit cleanly. Inspect `widget.log` for the full trail.

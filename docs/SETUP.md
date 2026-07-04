# Setup — Discord LaunchPad Widget

This is the one-time setup you have to do before the widget can run.
Total time: ~10 minutes.

## 1. Create a Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application**, give it any name (e.g. *LaunchPad*).
3. Open the **Activities** tab in the left sidebar.
4. Click **Profile Widget → Enable**.
5. Under **Data Fields**, add one field per row in the table below.

### Data Fields to create

Create a field for every row. The **Name** column is what the widget will
display; the **Value** column is sourced from the corresponding
identities payload key. Discord does not allow more than ~10 text fields
plus a couple of numeric/image fields, so pick the subset that matters to
you — the daemon always sends them all, Discord silently ignores the
unbound ones.

| Name                | Type   | Bound to identities field |
| ------------------- | ------ | ------------------------- |
| Mission             | text   | `mission`                 |
| Rocket              | text   | `rocket`                  |
| Provider            | text   | `provider`                |
| Status              | text   | `status`                  |
| Countdown           | text   | `countdown`               |
| Window              | text   | `window`                  |
| Site                | text   | `site`                    |
| Location            | text   | `location`                |
| Country             | text   | `country`                 |
| Orbit               | text   | `orbit`                   |
| Crew                | text   | `crew`                    |
| Type                | text   | `type`                    |
| Probability         | number | `probability`             |
| Image               | image  | `image`                   |

> ⚠️ Field names are case-sensitive and must match the daemon's output
> *exactly*. If you change a name here, also update `payload_builder.py`.

## 2. Create a bot (or use a user token)

The PATCH endpoint accepts both a `Bot` token and a user account token,
but `Bot` is the supported path.

1. In the Developer Portal, open **Bot** in the sidebar.
2. Click **Add Bot → Yes, do it**.
3. Copy the bot token — this is your `DISCORD_BOT_TOKEN`.
4. Make sure the **Message Content Intent** is **not** required (the daemon
   only sends a single PATCH; it doesn't read messages).

## 3. Collect IDs

* **Application ID** — from **General Information** in the Developer
  Portal. This is `DISCORD_APPLICATION_ID`.
* **User ID** — your own Discord user ID. Enable Developer Mode in
  Discord → Settings → Advanced → Developer Mode, then right-click your
  avatar → *Copy User ID*. This is `DISCORD_USER_ID`.

## 4. Add the secrets to GitHub

In your fork of this repository:

1. Settings → Secrets and variables → Actions → **New repository secret**
2. Add three secrets:
   * `DISCORD_APPLICATION_ID`
   * `DISCORD_USER_ID`
   * `DISCORD_BOT_TOKEN`

Optional:

* `NASA_API_KEY` — for higher NASA rate limits.
* Variables (not secrets, since they're not sensitive):
  * `PREFERRED_SOURCE` — `launch_library` or `spacex`.
  * `UPDATE_INTERVAL_SECONDS` — how often to refresh.
  * `DRY_RUN` — set to `true` to log payloads without PATCHing.

## 5. First run

1. Go to the **Actions** tab in your fork.
2. Select **Update LaunchPad Widget** on the left.
3. Click **Run workflow → Run workflow**.
4. Watch the logs — you should see a `PATCH ok` line within a minute.

Once the first run completes successfully, the workflow self-dispatches
subsequent runs every time it exits, so the widget stays live
indefinitely. The `schedule:` cron in `update.yml` is just a safety net.

## 6. (Optional) Image upload helper

If you want a custom image per launch instead of the bundled fallback,
set up the helper:

1. Create a private Discord channel the bot can access.
2. Copy the channel ID — this is `DISCORD_TARGET_CHANNEL_ID`.
3. Add `DISCORD_TARGET_CHANNEL_ID` as a repository variable (it's not
   sensitive but tying it to a secret is fine too).
4. Extend the workflow step that runs the daemon to also call
   `scripts/upload_image.py` and persist the resulting URL.

The helper uploads a local image and prints the Discord CDN URL on
stdout, so you can `$(python scripts/upload_image.py ...)` to capture it
into an environment variable for the next step.

# Rate Limits

This project hits several rate-limited APIs. Here's the math on what
gets used and what the limits are.

## Discord Widget PATCH

**Endpoint:**
```
PATCH https://discord.com/api/v9/applications/{APP_ID}/users/{USER_ID}/identities/0/profile
```

**Rate limit:** ~3 PATCHes per bucket (resets ~every ~40s based on live observation).

**Our usage:** At default `UPDATE_INTERVAL_SECONDS=300`, we PATCH once every 5 minutes = 12/hour. Well under the 3-per-40s = 270/hour limit.

**Why `MIN_PATCH_INTERVAL_SECONDS=60`:** The state-file de-dup mechanism means we don't PATCH if the payload didn't change, so most of the time we only PATCH when the countdown seconds actually tick.

## Launch Library 2

**Endpoint:**
```
GET https://ll.thespacedevs.com/2.3.0/launches/upcoming/
```

**Rate limit:** 15 requests/hour (free tier).

**Our usage:** We hit LL2 once per cycle. With `UPDATE_INTERVAL_SECONDS=300` and `CACHE_TTL_SECONDS=120`, the cache covers most cycles, so the actual hit rate is **~6 requests/hour** (one every 10 minutes due to cache miss every 2 min × 5-min interval).

**Fallback:** If we hit the LL2 limit, the daemon falls back to the SpaceX API automatically (no documented rate limit).

## SpaceX API

**Endpoint:**
```
GET https://api.spacexdata.com/v4/launches/upcoming
```

**Rate limit:** No documented cap. r-spacex hosts the API on a free public service.

**Our usage:** Only called when LL2 fails. Effectively never under normal operation.

## Image hosting (Discord CDN)

We upload images to a Discord channel and read back the `cdn.discordapp.com` URL. Discord's rate limit on channel message creation is:

- 5 messages per 5 seconds per channel
- 5 messages per bucket

**Our usage:** 1 message per cycle (every 5 minutes by default). Far under the limit.

The CDN URL itself is unlimited (Discord's CDN serves images freely).

## GitHub Actions

**Free tier:** 2,000 minutes/month.

**Our usage:** Each daemon run takes ~6 minutes. With self-dispatch every 5h50m:
- 24 hours × 4 runs/day = 4 runs/day
- 4 × 6 min = 24 min/day
- 30 days × 24 min = **720 min/month** (well within free tier)

For **public repos**: completely free.

For **private repos**: 2,000 min is shared across all private repos on the account. If you have multiple widget projects, the limit may get tight.

## Summary

| API | Limit | Our usage | Headroom |
| --- | --- | --- | --- |
| Discord PATCH | 3/bucket (~40s) | 1/5min | 20× |
| Discord CDN upload | 5/5s | 1/5min | 150× |
| Launch Library 2 | 15/hr | 6/hr | 2.5× |
| SpaceX API | None | 0/hr | ∞ |
| GitHub Actions | 2000 min/mo | 720 min/mo | 2.8× |

Every API has at least 2× headroom, so the daemon is safe to leave
running 24/7 on the free tier.

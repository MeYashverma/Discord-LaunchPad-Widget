# Rate limits

| Source              | Free tier         | Widget impact                                      |
| ------------------- | ----------------- | -------------------------------------------------- |
| Discord PATCH       | 5 / 5s per route  | Throttled by `MIN_PATCH_INTERVAL_SECONDS` ≥ 60s    |
| Launch Library 2    | 15 / hour         | Absorbed by `CACHE_TTL_SECONDS` ≥ 120s             |
| SpaceX API          | No documented cap | Same as above                                      |
| NASA APOD           | 30 / hour         | Bonus enrichment, never on the hot path            |
| GitHub Actions      | 2000 min/month    | ~5h50m × 4 runs/day × 30 days ≈ 350 min/month    |

## Why the daemon de-duplicates PATCHes

Every payload is hashed and stored in `last_payload.json`. If the hash
matches the last successful PATCH, the daemon logs *"Payload unchanged
since last PATCH; skipping."* and continues. This means:

* A static countdown at *T-30d* is one PATCH per minute max, not per
  second.
* When a new launch enters the window (or one scrubs), the new payload
  hashes differently and gets sent immediately.
* The 5 req / 5s Discord bucket is never threatened.

## Bumping against a 429

If you do see `429 from Discord` in `widget.log`, raise
`MIN_PATCH_INTERVAL_SECONDS` to `120` and the problem goes away. The
countdown will be a little coarser (it updates at most once every two
minutes) but the daemon will use far less of the bucket.

## Launch Library 2 hard cap

At 15 req/hr the per-cycle cost of LL2 is one request; the cache covers
the other ~239 cycles. If you ever raise the loop frequency above one
update per 4 minutes, increase `CACHE_TTL_SECONDS` proportionally.

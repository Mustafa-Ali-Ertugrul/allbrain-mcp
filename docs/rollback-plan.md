# AllBrain MCP v1.0.0 Rollback Plan & Post-Release Monitoring

This document details the contingency procedures and post-release telemetry metrics for safely rolling back from **v1.0.0** to **v0.4.1** if unrecoverable instability occurs.

---

## 1. Rollback Procedure (v1.0.0 → v0.4.1)

### Step 1: Git Tag & GitHub Release Rollback
```bash
# Delete local release tag
git tag -d v1.0.0

# Delete remote release tag
git push --delete origin v1.0.0

# Delete GitHub Release
gh release delete v1.0.0 --yes
```

### Step 2: Checkout Previous Stable Tag (v0.4.1)
```bash
# Checkout v0.4.1
git checkout v0.4.1

# Sync dependencies
uv sync --group dev
```

### Step 3: Database & State Restoration
The v1.0.0 database schema is backward-compatible with v0.4.1. If data corruption occurred during a failed run, restore the automatic pre-run snapshot:

```bash
# Restore backup database
cp ~/.allbrain/allbrain.db.bak-<timestamp> ~/.allbrain/allbrain.db
```

---

## 2. Post-Release Monitoring Plan (First 72 Hours)

During the first 72 hours post-release, monitor the following health metrics:

1. **Crash Rate**: Stdio server process terminations (`exit_code != 0`).
2. **Tool Error Rate**: Ratio of `ok=False` tool responses in telemetry logs.
3. **Queue Leases**: Unrecovered `state="leased"` records or excessive `LEASE_EXPIRED` events in `QueueItemRecord`.
4. **Replay Integrity**: Failure frequency during `EventReplayEngine` deterministic replay runs.
5. **SQLite WAL Growth**: Ensure `allbrain.db-wal` remains $\le 100$ MB under active load.
6. **Process Memory RSS**: Verify agent memory footprint remains $\le 512$ MB RSS.
7. **Average Tool Latency**: Monitor per-tool execution latency targeting $\le 200$ms.


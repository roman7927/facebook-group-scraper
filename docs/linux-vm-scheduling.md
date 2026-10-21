# Linux VM deployment

The home Facebook scraper runs on the Linux VM as two systemd units:

- `greencheck-api-tunnel.service` maintains a loopback-only SSH tunnel to the Green Check API on the droplet. It uses the droplet's key-only alternate SSH listener on port 2222 because the home network blocks outbound port 22.
- `greencheck-facebook-scraper.timer` starts one scraper cycle every hour and catches up after a VM reboot.

The VM never connects directly to PostgreSQL. All configuration, heartbeats, source outcomes, and record batches use the signed `/api/v1/scraper` contract through `127.0.0.1:18000`.

Runtime files in `/opt/greencheck-facebook-scraper` include `.env`, `facebook_state.json`, the configuration cache, workbook, and durable outbound queue. These files are not committed. The systemd service uses `flock` to prevent overlapping cycles.

Incremental collection confirms a stored-post boundary after three distinct
stored posts are visible. The confirmations may have pinned or newly ranked
posts between them; every unseen post through the final confirmation remains
eligible for collection. A progressing source has a bounded ten-minute ceiling,
while the no-progress and maximum-scroll guards stop stalled feeds earlier. A
source still refuses partial data unless it reaches the confirmed boundary or
the 50-new-post cap.

Useful commands:

```bash
sudo systemctl status greencheck-api-tunnel.service
sudo systemctl status greencheck-facebook-scraper.timer
sudo systemctl start greencheck-facebook-scraper.service
sudo journalctl -u greencheck-facebook-scraper.service
```

Do not disable the former Mac launchd jobs until a manual Linux cycle has completed, its signed heartbeat and source outcomes appear in Green Check, and the timer survives a VM restart.

## Expired Facebook sessions

The scraper checks rendered login forms on each group and comment page, including
forms that appear after navigation. Hidden hydration inputs alone are ignored.
A Facebook URL alone is not proof of a healthy session. An expired session is
reported as `logged_out` with a manual-login error in the signed heartbeat and
source outcomes. Account verification pages report `degraded`; do not attempt
to bypass them. A cycle with no successful groups exits nonzero without changing
the workbook.

To recover, use `login_and_save_state.py` interactively in a private temporary
directory with `umask 077`. The user must complete login and any Facebook
verification themselves. Transfer the resulting session over verified SSH to
the VM, validate authenticated group access there, then atomically replace the
runtime session under `.runtime/scrape.lock`, retaining the previous file as a
private backup. Never log or commit session contents. Run the existing Linux
wrapper and confirm fresh accepted batches in Green Check; a heartbeat alone
does not prove that collection or delivery succeeded.

### 2026-10-21 recovery checkpoint (UTC)

- VM `linuxmgmt` / `192.168.1.16`: deployed integrated main commit
  `c7ae45f9062ed450a8c9b65637b7a3d5edf4bc1b` from a Git archive under the
  existing runtime lock. `DEPLOYED_COMMIT` records that revision.
- Private pre-change backup:
  `/opt/greencheck-facebook-scraper/.runtime/session-recovery.h5OUgf`.
  Includes code, original login state, configuration, workbook, and a consistent
  SQLite queue backup. No queue records or workbook rows were deleted.
- All 30 offline tests passed on both Mac and VM.
- The live validation cycle exited 1 with explicit expired-session errors for
  all four groups; Green Check accepted the signed `logged_out` heartbeat.
  Workbook checksums matched the backup. The timer and API tunnel stayed active.
- Collection is **not yet restored** at this checkpoint: a dedicated local
  login window is awaiting user authentication. Validate the refreshed session
  on the VM before replacement, then run the wrapper and confirm fresh accepted
  batches and inserted post counts centrally. Last accepted batch before repair
  was `2026-10-01T02:02:34Z`.

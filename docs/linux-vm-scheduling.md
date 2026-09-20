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

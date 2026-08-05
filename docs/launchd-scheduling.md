# Green Check scraper scheduling on macOS

The scraper runs once per hour at minute zero and once after login. A separately supervised SSH tunnel starts at login and restarts after network interruptions. The scraper uses the local virtual environment, `.env`, durable queue, and heartbeat integration, and refuses to begin until the Agent health endpoint is reachable through the tunnel.

## Install

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.greencheck.facebook-scraper.plist ~/Library/LaunchAgents/
cp launchd/com.greencheck.api-tunnel.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.api-tunnel.plist 2>/dev/null || true
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.api-tunnel.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist
```

Open the SSH tunnel separately before a scheduled cycle. The wrapper never logs `.env` values, cookies, browser state, or signed headers.

## Status and logs

```bash
launchctl print gui/$(id -u)/com.greencheck.facebook-scraper
launchctl print gui/$(id -u)/com.greencheck.api-tunnel
tail -f logs/scraper.log
tail -f logs/scraper-error.log
```

## Manual run

```bash
scripts/run_greencheck_scraper.sh
```

## Remove

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.api-tunnel.plist
rm ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist
rm ~/Library/LaunchAgents/com.greencheck.api-tunnel.plist
```

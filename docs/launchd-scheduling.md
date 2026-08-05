# Green Check scraper scheduling on macOS

The job runs once per hour at minute zero and once after login. It uses the local virtual environment, `.env`, durable queue, and heartbeat integration.

## Install

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.greencheck.facebook-scraper.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist
launchctl kickstart -k gui/$(id -u)/com.greencheck.facebook-scraper
```

Open the SSH tunnel separately before a scheduled cycle. The wrapper never logs `.env` values, cookies, browser state, or signed headers.

## Status and logs

```bash
launchctl print gui/$(id -u)/com.greencheck.facebook-scraper
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
rm ~/Library/LaunchAgents/com.greencheck.facebook-scraper.plist
```

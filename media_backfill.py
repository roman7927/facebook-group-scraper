"""One-off, signed repair for legacy '[Post without text]' Facebook records."""
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from greencheck_adapter import build_payloads
from greencheck_client import GreenCheckClient
from main3 import ACTION_SCAN_JS, STATE_FILE, canonical_post_url, clean_text


def main():
    client = GreenCheckClient()
    config = client.config()
    sources = {item["group_id"]: item for item in config["groups"]}
    targets = client.media_backfill()["posts"]
    repaired = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(STATE_FILE), viewport={"width": 1400, "height": 1000})
        page = context.new_page()
        for number, target in enumerate(targets, 1):
            source = sources.get(target["group_id"])
            if not source:
                continue
            page.goto(target["post_url"], wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1200)
            scope = re.search(r"facebook\.com/groups/([^/?#]+)", target["post_url"])
            if not scope:
                continue
            cards = page.evaluate(ACTION_SCAN_JS, {"gid": scope.group(1), "actionSelector": "[aria-label^='Actions for this post by ']", "messageSelector": "div[data-ad-rendering-role='story_message']"})
            card = next((item for item in cards if canonical_post_url(item.get("direct_url", ""), scope.group(1))[0] == target["post_id"]), None)
            if card is None:
                print(f"{number}/{len(targets)} unresolved {target['post_id']}")
                continue
            repaired.append({**target, "group_name": source["group_name"], "post_text": clean_text(card.get("text")), **{key: card.get(key) for key in ("has_text", "has_image", "has_video", "has_link_preview", "attachment_count", "content_type")}})
            print(f"{number}/{len(targets)} {target['post_id']} {card.get('content_type')}")
        browser.close()
    for _, payload in build_payloads(repaired, [], client.client_id, "0.1.1-media-backfill", list(sources.values())):
        client.ingest(payload)
    print(f"Updated {len(repaired)} of {len(targets)} legacy placeholder posts.")


if __name__ == "__main__":
    main()

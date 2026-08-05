"""Convert scraper rows to the Green Check 1.0 payload without keyword filtering."""
import uuid
from datetime import datetime, timezone


def utc(value):
    if not value: return None
    if isinstance(value, str): value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def identifier(value):
    value = str(value or "")
    if not value or "e" in value.lower() or not value.isdigit(): return None
    return value


def source_identifier(value):
    value = str(value or "")
    if not value or ("e" in value.lower() and value.replace("e", "").replace("E", "").replace("+", "").replace("-", "").replace(".", "").isdigit()):
        return None
    return value


def build_payload(posts, comments, client_id, scraper_version, sources):
    batch_id = str(uuid.uuid4())
    configured = {source["group_id"]: source for source in sources}
    groups = {p["group_id"]: {"group_id": p["group_id"], "group_name": p.get("group_name", ""), "group_url": configured[p["group_id"]]["group_url"]} for p in posts if p["group_id"] in configured}
    mapped_posts = [{"group_id": source_identifier(p["group_id"]), "group_name": p.get("group_name", ""), "post_id": identifier(p["post_id"]), "post_datetime": utc(p.get("post_datetime")), "post_datetime_status": "parsed" if p.get("post_datetime") else "unavailable", "post_text": p.get("post_text", ""), "text_status": "complete", "displayed_poster": p.get("displayed_poster", ""), "poster_id": None, "poster_url": p.get("poster_url") or None, "post_url": p.get("post_url") or None} for p in posts]
    mapped_comments = [{"group_id": source_identifier(c["group_id"]), "group_name": c.get("group_name", ""), "post_id": identifier(c["post_id"]), "comment_id": None, "parent_comment_id": None, "comment_datetime": utc(c.get("comment_datetime")), "comment_text": c.get("comment_text", ""), "text_status": "complete", "commenter_name": c.get("commenter_name", ""), "commenter_id": identifier(c.get("commenter_id")), "commenter_url": None, "comment_url": None} for c in comments]
    if any(not p["group_id"] or not p["post_id"] for p in mapped_posts): raise ValueError("invalid Facebook post identifier")
    return batch_id, {"schema_version": "1.0", "client_id": client_id, "scraper_version": scraper_version, "batch_id": batch_id, "scraped_at": utc(datetime.now(timezone.utc)), "groups": list(groups.values()), "posts": mapped_posts, "comments": mapped_comments}

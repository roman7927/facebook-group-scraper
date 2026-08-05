"""Convert scraper rows to the Green Check 1.0 payload without keyword filtering."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

MAX_BATCH_RECORDS = 500


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


def _mapped_rows(posts, comments):
    mapped_posts = [{"group_id": source_identifier(p["group_id"]), "group_name": p.get("group_name", ""), "post_id": identifier(p["post_id"]), "post_datetime": utc(p.get("post_datetime")), "post_datetime_status": "parsed" if p.get("post_datetime") else "unavailable", "post_text": p.get("post_text", ""), "text_status": "complete", "displayed_poster": p.get("displayed_poster", ""), "poster_id": None, "poster_url": p.get("poster_url") or None, "post_url": p.get("post_url") or None} for p in posts]
    mapped_comments = [{"group_id": source_identifier(c["group_id"]), "group_name": c.get("group_name", ""), "post_id": identifier(c["post_id"]), "comment_id": None, "parent_comment_id": None, "comment_datetime": utc(c.get("comment_datetime")), "comment_text": c.get("comment_text", ""), "text_status": "complete", "commenter_name": c.get("commenter_name", ""), "commenter_id": identifier(c.get("commenter_id")), "commenter_url": None, "comment_url": None} for c in comments]
    if any(not p["group_id"] or not p["post_id"] for p in mapped_posts):
        raise ValueError("invalid Facebook post identifier")
    return mapped_posts, mapped_comments


def _batch_id(client_id, posts, comments):
    identity = json.dumps(
        {"client_id": client_id, "posts": posts, "comments": comments},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"greencheck:{digest}"))


def build_payloads(posts, comments, client_id, scraper_version, sources):
    """Build stable batches without splitting a post from its comments."""
    configured = {source["group_id"]: source for source in sources}
    mapped_posts, mapped_comments = _mapped_rows(posts, comments)
    comments_by_post = {}
    for comment in mapped_comments:
        key = (comment["group_id"], comment["post_id"])
        comments_by_post.setdefault(key, []).append(comment)

    chunks = []
    chunk_posts, chunk_comments = [], []
    for post in mapped_posts:
        post_comments = comments_by_post.pop(
            (post["group_id"], post["post_id"]), []
        )
        unit_size = 1 + len(post_comments)
        if unit_size > MAX_BATCH_RECORDS:
            raise ValueError("one post and its comments exceed the batch limit")
        if chunk_posts and len(chunk_posts) + len(chunk_comments) + unit_size > MAX_BATCH_RECORDS:
            chunks.append((chunk_posts, chunk_comments))
            chunk_posts, chunk_comments = [], []
        chunk_posts.append(post)
        chunk_comments.extend(post_comments)

    orphan_comments = [item for values in comments_by_post.values() for item in values]
    for offset in range(0, len(orphan_comments), MAX_BATCH_RECORDS):
        if chunk_posts or chunk_comments:
            chunks.append((chunk_posts, chunk_comments))
            chunk_posts, chunk_comments = [], []
        chunks.append(([], orphan_comments[offset:offset + MAX_BATCH_RECORDS]))
    if chunk_posts or chunk_comments:
        chunks.append((chunk_posts, chunk_comments))

    scraped_at = utc(datetime.now(timezone.utc))
    payloads = []
    for chunk_posts, chunk_comments in chunks:
        group_ids = {
            item["group_id"] for item in (*chunk_posts, *chunk_comments)
        }
        groups = [
            {"group_id": group_id,
             "group_name": configured[group_id]["group_name"],
             "group_url": configured[group_id]["group_url"]}
            for group_id in sorted(group_ids) if group_id in configured
        ]
        batch_id = _batch_id(client_id, chunk_posts, chunk_comments)
        payloads.append((batch_id, {
            "schema_version": "1.0", "client_id": client_id,
            "scraper_version": scraper_version, "batch_id": batch_id,
            "scraped_at": scraped_at, "groups": groups,
            "posts": chunk_posts, "comments": chunk_comments,
        }))
    return payloads


def build_payload(posts, comments, client_id, scraper_version, sources):
    """Backward-compatible helper for callers that expect one small batch."""
    payloads = build_payloads(posts, comments, client_id, scraper_version, sources)
    if len(payloads) != 1:
        raise ValueError("snapshot requires multiple Green Check batches")
    return payloads[0]

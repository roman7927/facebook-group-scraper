"""Normalize non-sensitive media evidence observed in one Facebook post card."""

CONTENT_TYPES = {
    "text", "text_with_image", "image_only", "text_with_video", "video_only",
    "link", "text_with_link", "attachment_only", "empty", "unknown",
}


def media_metadata(
    *,
    has_text: bool,
    has_image: bool = False,
    has_video: bool = False,
    has_link_preview: bool = False,
    attachment_count: int = 0,
    uncertain: bool = False,
) -> dict[str, bool | int | str]:
    """Classify only observed card-local evidence; never accept media URLs or content."""
    attachment_count = max(0, int(attachment_count))
    has_image = bool(has_image)
    has_video = bool(has_video)
    has_link_preview = bool(has_link_preview)
    has_text = bool(has_text)

    if uncertain:
        content_type = "unknown"
    elif has_video:
        content_type = "text_with_video" if has_text else "video_only"
    elif has_link_preview:
        content_type = "text_with_link" if has_text else "link"
    elif has_image:
        content_type = "text_with_image" if has_text else "image_only"
    elif attachment_count:
        content_type = "attachment_only"
    elif has_text:
        content_type = "text"
    else:
        content_type = "empty"
    return {
        "has_text": has_text,
        "has_image": has_image,
        "has_video": has_video,
        "has_link_preview": has_link_preview,
        "attachment_count": attachment_count,
        "content_type": content_type,
    }


def normalized_row_metadata(row: dict) -> dict[str, bool | int | str]:
    """Use card metadata when available; retain safe text-only defaults for legacy rows."""
    authored_text = str(row.get("post_text") or "").strip()
    if authored_text == "[Post without text]":
        authored_text = ""
    return media_metadata(
        has_text=bool(row.get("has_text", bool(authored_text))),
        has_image=bool(row.get("has_image", False)),
        has_video=bool(row.get("has_video", False)),
        has_link_preview=bool(row.get("has_link_preview", False)),
        attachment_count=row.get("attachment_count", 0),
        uncertain=row.get("content_type") == "unknown",
    )

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


def clean_url_text(url: str | None) -> str:
    return (url or "").replace("\n", "").replace("\r", "").replace("\t", "").strip()


def normalize_url(url: str | None) -> str:
    cleaned = clean_url_text(url)
    if not cleaned:
        return ""
    parts = urlsplit(cleaned)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def is_http_url(url: str | None) -> bool:
    return bool(normalize_url(url))


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_dedupe_key(
    canonical_url: str | None,
    url: str | None,
    guid: str | None,
    title: str | None,
    published_at: str | None,
    summary: str | None,
) -> str:
    canonical = normalize_url(canonical_url)
    if canonical:
        return f"canonical:{canonical}"
    normalized = normalize_url(url)
    if normalized:
        return f"url:{normalized}"
    clean_guid = (guid or "").strip()
    if clean_guid:
        return f"guid:{clean_guid}"
    material = f"{title or ''}{published_at or ''}{summary or ''}"
    return "hash:" + hashlib.sha256(material.encode("utf-8")).hexdigest()

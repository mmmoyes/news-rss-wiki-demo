from rsslab.dedupe import compute_dedupe_key, normalize_url


def test_normalize_url_removes_tracking_params_and_control_whitespace():
    url = "https://example.com/news/1\n\t?utm_source=feed&gclid=abc&id=42"

    assert normalize_url(url) == "https://example.com/news/1?id=42"


def test_compute_dedupe_key_prefers_canonical_then_url_then_guid_then_content():
    assert compute_dedupe_key("https://example.com/a", "https://example.com/b", "g", "t", "p", "s") == (
        "canonical:https://example.com/a"
    )
    assert compute_dedupe_key("", "https://example.com/b?utm_content=x", "g", "t", "p", "s") == (
        "url:https://example.com/b"
    )
    assert compute_dedupe_key("", "", "g", "t", "p", "s") == "guid:g"
    assert compute_dedupe_key("", "", "", "t", "p", "s").startswith("hash:")

"""cookies.txt fallback for IG session cookies (Windows: Chrome 127+ app-bound
encryption makes browser extraction impossible — yt-dlp #10927)."""

from __future__ import annotations

import pytest

from reels_scrap.ingest.collection import _ig_cookies

COOKIES = "\n".join(
    [
        "# Netscape HTTP Cookie File",
        "\t".join([".instagram.com", "TRUE", "/", "TRUE", "1819786643", "csrftoken", "abc"]),
        # httpOnly rows carry the #HttpOnly_ prefix — sessionid is one of them
        "\t".join(["#HttpOnly_.instagram.com", "TRUE", "/", "TRUE", "1819786643", "sessionid", "s3ss"]),
        "\t".join([".example.com", "TRUE", "/", "TRUE", "1819786643", "sessionid", "other"]),
        "",
    ]
)


def test_reads_httponly_sessionid(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text(COOKIES, encoding="utf-8")
    c = _ig_cookies(str(p))
    assert c == {"csrftoken": "abc", "sessionid": "s3ss"}


def test_rejects_file_without_sessionid(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text(COOKIES.replace("sessionid", "ds_user_id"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="sessionid"):
        _ig_cookies(str(p))

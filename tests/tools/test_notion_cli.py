import pytest

from src.tools.skills.notion import notion_cli


def test_build_url_accepts_full_url() -> None:
    url = notion_cli.build_url("https://api.notion.com/v1/search")
    assert url == "https://api.notion.com/v1/search"


def test_build_url_prefixes_base() -> None:
    url = notion_cli.build_url("/v1/search")
    assert url == "https://api.notion.com/v1/search"


def test_parse_query_pairs() -> None:
    parsed = notion_cli.parse_query_args(["a=1", "b=two"])
    assert parsed == {"a": "1", "b": "two"}


def test_parse_query_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        notion_cli.parse_query_args(["missing_equals"])


def test_build_headers_includes_version_and_auth() -> None:
    headers = notion_cli.build_headers(
        api_key="token", version="2025-09-03", has_body=True
    )
    assert headers["Authorization"] == "Bearer token"
    assert headers["Notion-Version"] == "2025-09-03"
    assert headers["Content-Type"] == "application/json"

import httpx

from src.agents.provider_errors import extract_provider_error_details


def test_extract_provider_error_details_from_httpx_status_error() -> None:
    request = httpx.Request(
        "POST",
        "https://api.groq.com/openai/v1/chat/completions",
        json={"model": "x", "messages": []},
    )
    response = httpx.Response(
        400,
        request=request,
        headers={"x-request-id": "req_123"},
        json={
            "error": {
                "message": "tool_choice is required but did not call a tool",
                "type": "invalid_request_error",
                "code": "invalid_tool_choice",
                "request_id": "req_123",
            }
        },
    )
    exc = httpx.HTTPStatusError("Bad Request", request=request, response=response)

    details = extract_provider_error_details(exc)

    assert details is not None
    assert details.status_code == 400
    assert details.request_id == "req_123"
    assert details.error_type == "invalid_request_error"
    assert details.error_code == "invalid_tool_choice"
    assert "tool_choice is required" in (details.message or "")
    assert details.raw_body_excerpt is None


def test_extract_provider_error_details_falls_back_to_body_excerpt_when_not_json() -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(
        400,
        request=request,
        headers={"x-request-id": "req_999"},
        text="<html>not json</html>",
    )
    exc = httpx.HTTPStatusError("Bad Request", request=request, response=response)

    details = extract_provider_error_details(exc)

    assert details is not None
    assert details.status_code == 400
    assert details.request_id == "req_999"
    assert details.message is None
    assert details.raw_body_excerpt is not None
    assert "not json" in details.raw_body_excerpt

from src.agents.messages import ConfirmationResponse


def test_confirmation_response_schema_is_strict() -> None:
    schema = ConfirmationResponse.model_json_schema()

    # Pydantic v2 uses JSON Schema Draft 2020-12 style.
    # With extra='forbid', top-level should forbid additional properties.
    assert schema.get("additionalProperties") is False

    props = schema.get("properties", {})
    assert set(props.keys()) == {"content", "is_error"}

import pytest

from src.cyberagent.channels.telegram import stt


def test_require_key_reads_onepassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(stt, "get_secret", lambda *_args, **_kwargs: "vault-key")

    assert stt._require_key("groq") == "vault-key"

import json

from src.cyberagent.cli import suggestion_queue


def test_enqueue_suggestion_writes_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(suggestion_queue, "SUGGEST_QUEUE_DIR", tmp_path)
    path = suggestion_queue.enqueue_suggestion("hello")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["payload_text"] == "hello"


def test_read_queued_suggestions_returns_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(suggestion_queue, "SUGGEST_QUEUE_DIR", tmp_path)
    suggestion_queue.enqueue_suggestion("first")
    suggestion_queue.enqueue_suggestion("second")

    queued = suggestion_queue.read_queued_suggestions()
    texts = [item.payload_text for item in queued]
    assert texts == ["first", "second"]

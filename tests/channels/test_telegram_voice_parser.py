from __future__ import annotations

from src.cyberagent.channels.telegram import parser


def test_extract_voice_messages_parses_voice() -> None:
    updates = [
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "from": {"id": 42},
                "chat": {"id": 99},
                "voice": {
                    "file_id": "file-123",
                    "file_unique_id": "uniq-1",
                    "duration": 12,
                    "mime_type": "audio/ogg",
                },
            },
        }
    ]

    messages = parser.extract_voice_messages(updates)

    assert messages == [
        parser.TelegramInboundVoiceMessage(
            update_id=1,
            chat_id=99,
            user_id=42,
            message_id=10,
            file_id="file-123",
            file_unique_id="uniq-1",
            duration=12,
            mime_type="audio/ogg",
            file_name=None,
        )
    ]


def test_extract_voice_messages_parses_audio() -> None:
    updates = [
        {
            "update_id": 2,
            "message": {
                "message_id": 11,
                "from": {"id": 7},
                "chat": {"id": 5},
                "audio": {
                    "file_id": "file-abc",
                    "file_unique_id": "uniq-2",
                    "duration": 20,
                    "mime_type": "audio/mpeg",
                    "file_name": "voice.mp3",
                },
            },
        }
    ]

    messages = parser.extract_voice_messages(updates)

    assert messages == [
        parser.TelegramInboundVoiceMessage(
            update_id=2,
            chat_id=5,
            user_id=7,
            message_id=11,
            file_id="file-abc",
            file_unique_id="uniq-2",
            duration=20,
            mime_type="audio/mpeg",
            file_name="voice.mp3",
        )
    ]

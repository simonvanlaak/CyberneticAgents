# Telegram Integration PRD

## Overview
This document outlines the requirements for integrating **Telegram** as a communication channel for the CyberneticAgents system. The integration will allow agents to:
- Receive messages from Telegram users
- Send responses back to Telegram chats
- Support both direct messages and group interactions
- Provide a seamless user experience with proper formatting and media support

---

## Goals

### Primary Objectives
1. Enable agents to interact with users via Telegram bot interface
2. Support real-time bidirectional communication
3. Maintain conversation context across sessions
4. Provide secure authentication and authorization

### Success Criteria
- ✅ Bot can receive and process text messages from users
- ✅ Bot can send formatted text responses with Markdown support
- ✅ Conversation history is properly tracked and linked to agent sessions
- ✅ Users can authenticate securely with the bot
- ✅ Bot supports both 1:1 and group chat scenarios

## Dependencies
Depends on docs/product_requirements/communication_channels.md

## Out of Scope (Phase 1)
- Speech-to-Text pipeline (see docs/product_requirements/speech_to_text.md)

---

## User Stories

### As a User
- I want to interact with my agent via Telegram so I can access it from any device
- I want my conversations to be private and secure
- I want to use Telegram's rich formatting (bold, italic, code blocks, etc.)
- I want to send images/files and have the agent process them
- I want to send voice messages and have them transcribed automatically (STT)
- I want to receive timely notifications from my agent

### As a Developer
- I want to configure the Telegram integration via environment variables
- I want clear error handling and logging for debugging
- I want the integration to follow the existing tool/executor pattern
- I want to reuse existing agent infrastructure without duplication

---

## Technical Requirements

### 1. **Bot Configuration**
- Use Telegram Bot API (HTTP-based, no persistent connections required initially)
- Store bot token securely via 1Password integration
- Support webhook-based message receiving (scalable, preferred) and/or polling (fallback)

**Environment Variables:**
```bash
TELEGRAM_BOT_TOKEN=op://CyberneticAgents/TELEGRAM_BOT_TOKEN/credential
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=op://CyberneticAgents/TELEGRAM_WEBHOOK_SECRET/credential
```

### 2. **Message Handling**

**Inbound Messages:**
- Text messages
- Commands (e.g., `/start`, `/help`, `/reset`)
- Media (photos, documents)
- Voice messages (with automatic STT transcription)
- Audio files (with automatic STT transcription)
- Location data
- Inline keyboard responses

**Outbound Messages:**
- Formatted text (Markdown/HTML)
- Media (images, documents)
- Inline keyboards for interactive responses
- Reply-to for context preservation
- Edit message support for streaming responses

### 3. **Architecture**

**Components:**
```
src/cyberagent/channels/
├── telegram/
│   ├── __init__.py
│   ├── bot.py              # Main bot class (Telegram API client)
│   ├── webhook.py          # Webhook handler (FastAPI/Flask endpoint)
│   ├── handlers.py         # Message/command handlers
│   ├── formatters.py       # Message formatting (Markdown, etc.)
│   ├── auth.py             # User authentication/authorization
│   └── stt.py              # Speech-to-Text service integration
```

**Integration Points:**
- `src/cyberagent/core/session_manager.py` - Link Telegram user IDs to agent sessions
- `src/cyberagent/core/message_router.py` - Route messages to appropriate agents
- `src/tools/` - Expose Telegram send capabilities as a tool for agents

### 4. **Session Management**
- Map Telegram `user_id` + `chat_id` to agent session IDs
- Store session metadata (user info, chat type, preferences)
- Support session reset/clear commands
- Implement session timeout and cleanup

**Session Storage Schema:**
```python
TelegramSession:
    telegram_user_id: int
    telegram_chat_id: int
    agent_session_id: str
    user_info: dict  # First name, last name, username
    chat_type: str   # "private", "group", "supergroup", "channel"
    created_at: datetime
    last_activity: datetime
    context: dict    # Custom context/state
```

### 5. **Speech-to-Text (STT) Integration (Future)**

Out of scope for this implementation. See docs/product_requirements/speech_to_text.md.

Voice messages are a core feature of Telegram and significantly improve user experience for longer inputs. STT integration should be seamless and reliable.

**Supported Audio Formats:**
- Telegram voice messages (`.ogg` with Opus codec)
- Audio files (`.mp3`, `.wav`, `.m4a`, `.ogg`)
- Video notes (extract audio track)

**STT Provider Options:**
1. **Groq Whisper** (Recommended - Fast & Accurate)
   - `whisper-large-v3` or `whisper-large-v3-turbo`
   - Free tier available
   - Very low latency (~1-2 seconds for 1 minute audio)
   - Supports 99+ languages

2. **OpenAI Whisper API**
   - `whisper-1` model
   - Pay-per-use pricing
   - Excellent accuracy
   - Supports 57+ languages

3. **Local Whisper** (Fallback)
   - Run `whisper.cpp` or `faster-whisper` locally
   - No API costs
   - Higher latency, requires GPU for speed
   - Full privacy (no data leaves server)

**Processing Flow:**
```
1. User sends voice message to bot
2. Telegram webhook delivers audio file URL
3. Download audio file from Telegram servers
4. Convert to compatible format if needed (ffmpeg)
5. Send to STT provider API
6. Receive transcription
7. Process transcription as text message
8. Optionally: Store original audio + transcript for reference
9. Delete temporary audio file
```

**Implementation Details:**

**Environment Variables:**
```bash
TELEGRAM_STT_PROVIDER=groq  # groq|openai|local
TELEGRAM_STT_MODEL=whisper-large-v3-turbo
TELEGRAM_STT_LANGUAGE=auto  # auto-detect or specify (en, de, es, etc.)
GROQ_API_KEY=op://CyberneticAgents/GROQ_API_KEY/credential
OPENAI_API_KEY=op://CyberneticAgents/OPENAI_API_KEY/credential
TELEGRAM_AUDIO_CACHE_DIR=/tmp/telegram_audio  # Temporary storage
TELEGRAM_STT_MAX_DURATION=300  # Max audio length in seconds (5 min)
```

**Code Structure:**
```python
# src/cyberagent/channels/telegram/stt.py

class STTService:
    """Speech-to-Text service for Telegram voice messages."""
    
    async def transcribe_voice_message(
        self,
        file_id: str,
        file_url: str,
        language: str = "auto"
    ) -> TranscriptionResult:
        """
        Download and transcribe a Telegram voice message.
        
        Returns:
            TranscriptionResult with text, language, duration, confidence
        """
        pass
    
    async def download_audio(self, file_url: str) -> bytes:
        """Download audio file from Telegram."""
        pass
    
    async def transcribe_with_groq(self, audio_bytes: bytes) -> str:
        """Transcribe using Groq Whisper API."""
        pass
    
    async def transcribe_with_openai(self, audio_bytes: bytes) -> str:
        """Transcribe using OpenAI Whisper API."""
        pass
    
    async def transcribe_local(self, audio_path: str) -> str:
        """Transcribe using local Whisper model."""
        pass
```

**User Experience:**
- Voice messages are transcribed automatically (no user action needed)
- Show typing indicator while transcribing
- Reply to the voice message with the transcription for transparency
- Fall back to "Could not transcribe audio" on error
- Support both voice messages and audio file uploads

**Performance Considerations:**
- Queue audio processing for long messages (>1 min)
- Cache transcriptions (file_id → transcript) to avoid re-processing
- Set max duration limit to prevent abuse (default: 5 minutes)
- Monitor API costs and rate limits

**Privacy & Security:**
- Delete downloaded audio files immediately after transcription
- Don't store audio long-term unless explicitly enabled
- Respect user preferences (opt-out option)
- Log transcription metadata (duration, language) not content

**Error Handling:**
- Network errors → Retry with exponential backoff
- STT API errors → Try fallback provider
- Audio format errors → Convert with ffmpeg
- Timeout → Cancel and notify user
- Rate limits → Queue and process later

### 6. **Security & Privacy**
- Verify webhook requests using secret token
- Validate message origins
- Implement user allowlist/blocklist
- Rate limiting per user/chat
- Encrypt sensitive data at rest
- Audit logging for all interactions

### 7. **Error Handling**
- Graceful handling of Telegram API errors (rate limits, network issues)
- STT transcription errors (unsupported format, API failures, timeouts)
- User-friendly error messages
- Retry logic for failed message sends and transcriptions
- Dead letter queue for unprocessable messages
- Fallback STT providers when primary fails

---

## API Design

### Webhook Endpoint
```http
POST /telegram/webhook
Content-Type: application/json
X-Telegram-Bot-Api-Secret-Token: <secret>

{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 123456789,
      "first_name": "John",
      "username": "johndoe"
    },
    "chat": {
      "id": 123456789,
      "type": "private"
    },
    "date": 1234567890,
    "text": "Hello, agent!"
  }
}
```

### Agent Tool Interface
```python
# Agents can send Telegram messages via tool
send_telegram_message(
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
    reply_to_message_id: int | None = None,
    keyboard: dict | None = None
)
```

---

## Implementation Phases

### Phase 1: Basic Bot (MVP)
- ✅ Bot token configuration
- ✅ Webhook setup
- ✅ Text message receive/send
- ✅ Basic session mapping
- ✅ `/start` and `/help` commands

### Phase 2: Rich Features
- Markdown formatting support
- Image/file handling
- Inline keyboards
- Message editing (for streaming)
- **Voice message transcription (STT)** ⭐
- Audio file transcription

### Phase 3: Advanced Features
- Group chat support
- User authentication/authorization
- Admin commands
- Analytics/usage tracking
- Multi-language support

---

## Dependencies

### Python Libraries
```text
python-telegram-bot>=20.0  # Official Telegram Bot API wrapper
fastapi>=0.100.0           # Webhook server (if not already present)
uvicorn>=0.23.0            # ASGI server (if not already present)
groq>=0.4.0                # Groq API client (for Whisper STT)
openai>=1.0.0              # OpenAI API client (alternative STT)
ffmpeg-python>=0.2.0       # Audio format conversion
```

### External Services
- Telegram Bot API (https://api.telegram.org/bot<token>/)
- 1Password for secret management
- Webhook hosting (requires public URL)
- **Groq API** (for Whisper STT) - https://groq.com
- **OpenAI API** (optional, for Whisper STT fallback)

### System Dependencies
```bash
# Required for audio processing
sudo apt-get install ffmpeg  # Ubuntu/Debian
brew install ffmpeg          # macOS
```

---

## Configuration Example

```yaml
# config/channels.yaml
telegram:
  enabled: true
  bot_token_ref: "op://CyberneticAgents/TELEGRAM_BOT_TOKEN/credential"
  webhook:
    enabled: true
    url: "${TELEGRAM_WEBHOOK_URL}"
    secret_ref: "op://CyberneticAgents/TELEGRAM_WEBHOOK_SECRET/credential"
    path: "/telegram/webhook"
  polling:
    enabled: false  # Fallback if webhook not available
    interval: 1.0   # seconds
  features:
    markdown: true
    html: false
    inline_keyboards: true
    media: true
    stt: true  # Enable voice message transcription
  stt:
    provider: "groq"  # groq|openai|local
    model: "whisper-large-v3-turbo"  # groq: whisper-large-v3-turbo, openai: whisper-1
    language: "auto"  # auto-detect or specify (en, de, es, fr, etc.)
    max_duration: 300  # seconds (5 minutes)
    cache_transcriptions: true  # Cache by file_id to avoid re-processing
    show_transcription: true  # Reply with transcription for transparency
    api_keys:
      groq_ref: "op://CyberneticAgents/GROQ_API_KEY/credential"
      openai_ref: "op://CyberneticAgents/OPENAI_API_KEY/credential"
  limits:
    max_message_length: 4096
    rate_limit_per_user: 30  # messages per minute
```

---

## Testing Strategy

### Unit Tests
- Message parsing and formatting
- Session management logic
- Handler routing
- STT service (mock Groq/OpenAI API responses)
- Audio download and format conversion

### Integration Tests
- Mock Telegram API responses
- Webhook request validation
- End-to-end message flow

### Manual Testing Checklist
- [ ] Bot responds to `/start`
- [ ] Bot handles text messages
- [ ] Bot sends formatted Markdown
- [ ] Bot works in group chats
- [ ] Webhook signature validation works
- [ ] Rate limiting triggers correctly
- [ ] Session persistence across restarts
- [ ] Voice messages are transcribed correctly
- [ ] Audio files are transcribed correctly
- [ ] STT works with different languages
- [ ] STT fallback works when primary provider fails
- [ ] Long audio messages (>1 min) are handled properly
- [ ] Audio transcription errors show user-friendly messages

---

## Monitoring & Observability

### Metrics to Track
- Messages received/sent per minute
- Response latency (receive → send)
- Error rate by error type
- Active users/sessions
- Webhook delivery success rate
- **STT transcription metrics:**
  - Voice messages received per hour
  - Transcription success rate
  - Transcription latency (average/p95/p99)
  - Audio duration distribution
  - API costs (Groq/OpenAI usage)
  - Transcription language distribution
  - Cache hit rate (avoided re-transcriptions)

### Logging
- All inbound messages (sanitized)
- All outbound messages
- Errors and exceptions
- Session lifecycle events
- API rate limit hits
- **STT-specific logs:**
  - Voice message metadata (duration, file size, language detected)
  - Transcription requests/responses (without audio content)
  - STT API errors and fallbacks
  - Audio conversion errors
  - Cache hits/misses

---

## Migration & Rollout

### Preparation
1. Create Telegram bot via @BotFather
2. Store bot token in 1Password
3. Set up webhook endpoint (requires HTTPS)
4. Configure environment variables

### Deployment
1. Deploy webhook endpoint
2. Register webhook with Telegram API
3. Enable feature flag
4. Monitor logs for errors
5. Gradual rollout to users

### Rollback Plan
- Disable webhook registration
- Fall back to polling mode (if implemented)
- Revert to previous version

---

## Open Questions

1. **Webhook vs Polling**: Should we support both or pick one?
   - *Recommendation*: Start with webhook (more efficient), add polling as fallback

2. **Multi-agent support**: How to handle users with multiple agents?
   - *Recommendation*: Use command prefix (e.g., `/agent1`, `/agent2`) or separate bots

3. **Group chat permissions**: Who can invoke the agent in a group?
   - *Recommendation*: Configurable allowlist of user IDs

4. **Message threading**: How to handle conversation context in groups?
   - *Recommendation*: Use reply-to to maintain thread context

5. **STT privacy**: Should we store transcriptions or delete immediately?
   - *Recommendation*: Delete audio files immediately after transcription; optionally cache transcription text by file_id for efficiency (not the audio itself)

6. **STT language detection**: Auto-detect or ask users to configure?
   - *Recommendation*: Start with auto-detect (works well), add user preference override later

7. **STT response format**: Show transcription to user or process silently?
   - *Recommendation*: Reply with transcription first (transparency), then process as text message. Configurable via settings.

---

## References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [python-telegram-bot Library](https://github.com/python-telegram-bot/python-telegram-bot)
- [Telegram Bot Best Practices](https://core.telegram.org/bots/webhooks)
- [Groq Whisper API](https://console.groq.com/docs/speech-text)
- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text)
- [ffmpeg Documentation](https://ffmpeg.org/documentation.html)
- [CyberneticAgents Secret Management](./secret_management.md)

---

## Success Metrics

### Week 1 (MVP)
- Bot deployed and responding to `/start`
- 10+ successful test conversations

### Month 1
- 50+ active users
- <2% error rate
- <500ms average response time

### Month 3
- Group chat support live
- Media handling functional
- **Voice message transcription live with >95% accuracy**
- **Average STT latency <3 seconds**
- 95%+ user satisfaction

---

## Appendix

### Example Bot Commands
```
/start - Initialize conversation with the agent
/help - Show available commands
/reset - Clear conversation history
/status - Show agent status
/settings - Configure agent preferences
```

### Example Inline Keyboard
```python
keyboard = {
    "inline_keyboard": [
        [
            {"text": "Yes", "callback_data": "confirm_yes"},
            {"text": "No", "callback_data": "confirm_no"}
        ]
    ]
}
```

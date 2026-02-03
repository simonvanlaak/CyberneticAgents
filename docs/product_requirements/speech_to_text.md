# Speech-to-Text (STT) Feature

## Overview
The Speech-to-Text (STT) feature enables CyberneticAgents to accept voice input from users via audio files, transcribe it to text, and process it as commands or messages. This makes the system accessible via voice interfaces and enables hands-free operation.

## Problem Statement
Text-based interfaces are limiting in scenarios where:
- Users are mobile or multitasking and cannot type
- Voice is a more natural input modality (calls, voice memos, meetings)
- Accessibility is required for users with typing difficulties
- Multi-modal input is needed (combining voice, text, images)

CyberneticAgents needs a robust STT pipeline to bridge voice input with its text-based command processing.

## Goals
1. **Accurate Transcription**: Convert speech to text with high accuracy
2. **Low Latency**: Process audio in near real-time for interactive use
3. **English-Only Support**: Handle English transcription only
4. **Integration**: Seamless integration with existing CLI, inbox, and agent workflows
5. **Cost Efficiency**: Minimize transcription costs while maintaining quality

## Use Cases

### 1. Voice Messages in Inbox
Users send voice messages via messaging platforms (Telegram):
1. Audio file arrives at System4 inbox
2. STT transcribes the audio
3. Transcribed text is processed as a message

## Out of Scope (Phase 1)
- Noise reduction / audio enhancement preprocessing
- Long-audio chunking
- Real-time microphone streaming
- WhatsApp or Twilio/VoIP integration
- Agent-skill API hook beyond the standalone tool script

## Architecture

### STT Pipeline
```
Audio Input → Transcription Model → Text Output
```

### Components

#### 1. Audio Input Handler
- **Supported Formats**: WAV, MP3, OGG, FLAC, M4A
- **Sources**:
  - File uploads (CLI, inbox)
  - Messaging platform attachments (Telegram)

#### 2. Audio Preprocessing
Deferred (out of scope for Phase 1).

#### 3. Transcription Engine
**Primary Model: OpenAI Whisper**
- API: OpenAI Whisper API
- Cost: $0.006 per minute (~$0.36/hour)

**Fallback: Groq Whisper**
- API: Groq's hosted Whisper model (ultra-low latency)
- Models:
  - `whisper-large-v3`: High accuracy, English
  - `whisper-large-v3-turbo`: Faster, slightly lower accuracy
- Cost: ~$0.05 per hour of audio


#### 4. Post-Processing
- **Punctuation & Capitalization**: Lightweight normalization (capitalize first letter, add sentence-ending punctuation when appropriate)
- **Timestamp Injection**: Add timestamps for long transcripts

## Implementation

### Phase 1: File-Based Transcription
- **Deliverable**: CLI command to transcribe audio files
- **Components**:
  - Audio file reader
  - OpenAI Whisper API integration (Groq fallback)
  - Text output to CLI
 - **Status**: Implemented (CLI command + file ingest live).

```python
# src/stt/transcribe.py
import openai

def transcribe_file(audio_path: str, provider="openai", model="whisper-1"):
    client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
    
    with open(audio_path, "rb") as audio:
        transcript = client.audio.transcriptions.create(
            model=model,
            file=audio,
            response_format="verbose_json",  # includes timestamps
            language="en"
        )
    
    return transcript.text, transcript.segments
```

### Phase 2: Inbox Integration
- **Deliverable**: Auto-transcribe voice messages from Telegram
- **Flow**:
  1. Voice message arrives → System4 inbox
  2. Detect audio attachment
  3. Download audio file
  4. Transcribe via STT
  5. Store transcript in inbox with original audio reference

```python
# src/stt/inbox_integration.py
def handle_voice_message(message):
    audio_path = download_audio(message.audio_url)
    transcript, segments = transcribe_file(audio_path)
    
    message.text = transcript
    message.metadata["stt_provider"] = "openai"
    
    inbox.add_message(message)
```

## Inbox Integration

### Automatic Transcription
When a voice message arrives:
1. **Detection**: inbox detects audio attachment
2. **Transcription**: STT transcribes audio
3. **Storage**: Transcript stored; audio deleted after transcription
4. **Display**: Inbox shows transcript (no retained audio)

```bash
$ cyberagent inbox

[VOICE] Simon van Laak (2 min ago):
  📎 audio.ogg (36s)
  "Hey, can you deploy the staging environment and let me know when it's ready?"
  
  Reply? (y/n):
```

### Voice Reply (Future Enhancement)
Deferred.

## Cost Estimates

### OpenAI Whisper (Primary)
- **Cost**: $0.006 per minute (~$0.36 per hour)
- **Speed**: Fast (<2s for 1-minute audio)
- **Best For**: High-quality transcription, primary

### Groq Whisper (Fallback)
- **Cost**: ~$0.05 per hour of audio
- **Speed**: Ultra-fast (<1s for 1-minute audio)
- **Best For**: Real-time, fallback

### Local Whisper
- **Cost**: Free (compute cost only)
- **Speed**: Slow (~5-10s for 1-minute audio)
- **Best For**: Privacy-sensitive, offline use

**Example Monthly Cost (100 hours of audio):**
- Groq: $5/month
- OpenAI: $36/month
- Local: $0 (but requires GPU)

## Error Handling

### Common Issues
1. **Audio Format Not Supported**
   - Solution: Auto-convert to WAV using `ffmpeg`
   
2. **Audio Too Long**
   - Solution: Reject with a clear message (chunking out of scope for Phase 1)
   
3. **Low Audio Quality**
   - Solution: Warn user if confidence is low (noise reduction out of scope for Phase 1)
   

### Fallback Strategy
```python
def transcribe_with_fallback(audio_path):
    try:
        return groq_transcribe(audio_path)
    except GroqError as e:
        logger.warning(f"Groq failed: {e}, falling back to OpenAI")
        return openai_transcribe(audio_path)
    except OpenAIError as e:
        logger.error(f"OpenAI failed: {e}")
```

## Security & Privacy

### Audio Storage
- **Temporary Files**: Delete after transcription (including Telegram audio)

## Integration Points

### CLI
- `cyberagent transcribe <file>`

### Inbox
- Auto-transcribe voice messages from messaging platforms
- Display transcript in inbox (no retained audio)

### Messaging Channels
- Telegram: Receive voice messages, auto-transcribe

### Agent Skills
Standalone tool script only; no agent-skill API hook in Phase 1.

## Future Enhancements
- **Emotion Detection**: Detect tone, sentiment in voice
- **Streaming Mic Capture**: Real-time microphone streaming
- **Long-Audio Chunking**: Automatically split and transcribe long audio
- **Voice Channel Expansion**: WhatsApp or Twilio/VoIP integrations
- **Audio Preprocessing**: Noise reduction and enhancement

## References
- [Groq Whisper API](https://console.groq.com/docs/speech-text)
- [OpenAI Whisper](https://platform.openai.com/docs/guides/speech-to-text)
- [Whisper GitHub](https://github.com/openai/whisper)
- [Pyannote Audio (Speaker Diarization)](https://github.com/pyannote/pyannote-audio)

## Related Features
- TTS (Text-to-Speech) for voice replies
- Agent Inbox for message routing
- Messaging Channels (Telegram)
- CLI for voice command execution

## How to Test
1. Record a 30-second voice message
2. Run `cyberagent transcribe test.wav`
3. Verify accuracy of transcription
4. Send voice message via Telegram
5. Verify auto-transcription in inbox
6. Test fallback by disabling OpenAI, verify Groq is used

## Notes For Resuming Later
- Telegram STT uses Groq/OpenAI endpoints directly via `requests` and now requests `verbose_json` for segments.
- Long audio is rejected by duration in Telegram (`TELEGRAM_STT_MAX_DURATION`), which matches Phase 1 scope.
- Telegram STT config supports provider fallback via env, but none of that is exposed in a CLI or config file.

## Implementation Checklist
- [x] CLI file-based transcription (`cyberagent transcribe <file>`)
- [x] English-only transcription enforced
- [x] OpenAI primary with Groq fallback (CLI module)
- [x] Telegram voice messages auto-transcribed
- [x] Inbox stores Telegram transcript (no retained audio)
- [x] Post-processing for punctuation/capitalization beyond provider defaults
- [x] Timestamp injection for long transcripts
- [x] Auto-convert unsupported audio to WAV via `ffmpeg`
- [x] Low-audio-quality warning

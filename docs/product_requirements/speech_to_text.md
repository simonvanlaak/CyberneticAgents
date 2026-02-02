# Speech-to-Text (STT) Feature

## Overview
The Speech-to-Text (STT) feature enables CyberneticAgents to accept voice input from users via audio files or real-time streaming, transcribe it to text, and process it as commands or messages. This makes the system accessible via voice interfaces and enables hands-free operation.

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
3. **Multi-Language Support**: Handle multiple languages and accents
4. **Integration**: Seamless integration with existing CLI, inbox, and agent workflows
5. **Cost Efficiency**: Minimize transcription costs while maintaining quality

## Use Cases

### 1. Voice Messages in Inbox
Users send voice messages via messaging platforms (Telegram, WhatsApp):
1. Audio file arrives at System4 inbox
2. STT transcribes the audio
3. Transcribed text is processed as a message

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
  - Real-time microphone stream
  - Messaging platform attachments (Telegram, WhatsApp)
  - Phone calls (via Twilio/VoIP integration)

#### 2. Audio Preprocessing
Deferred.

#### 3. Transcription Engine
**Primary Model: Groq Whisper**
- API: Groq's hosted Whisper model (ultra-low latency)
- Models:
  - `whisper-large-v3`: High accuracy, all languages
  - `whisper-large-v3-turbo`: Faster, slightly lower accuracy
- Cost: ~$0.05 per hour of audio

**Fallback: OpenAI Whisper**
- API: OpenAI Whisper API
- Cost: $0.006 per minute (~$0.36/hour)


#### 4. Post-Processing
- **Punctuation & Capitalization**: Auto-insert based on context
- **Timestamp Injection**: Add timestamps for long transcripts
- **Language Detection**: Auto-detect input language

## Implementation

### Phase 1: File-Based Transcription
- **Deliverable**: CLI command to transcribe audio files
- **Components**:
  - Audio file reader
  - Groq Whisper API integration
  - Text output to CLI
 - **Status**: Not implemented yet (CLI command + file ingest missing).

```python
# src/stt/transcribe.py
import groq

def transcribe_file(audio_path: str, provider="groq", model="whisper-large-v3-turbo"):
    client = groq.Client(api_key=os.getenv("GROQ_API_KEY"))
    
    with open(audio_path, "rb") as audio:
        transcript = client.audio.transcriptions.create(
            model=model,
            file=audio,
            response_format="verbose_json",  # includes timestamps
            language="en"  # or auto-detect
        )
    
    return transcript.text, transcript.segments
```

### Phase 2: Inbox Integration
- **Deliverable**: Auto-transcribe voice messages from Telegram/WhatsApp
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
    message.metadata["original_audio"] = audio_path
    message.metadata["stt_provider"] = "groq"
    
    inbox.add_message(message)
```

## Inbox Integration

### Automatic Transcription
When a voice message arrives:
1. **Detection**: inbox detects audio attachment
2. **Transcription**: STT transcribes audio
3. **Storage**: Both audio and transcript stored
4. **Display**: Inbox shows transcript with audio icon

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

### Groq Whisper
- **Cost**: ~$0.05 per hour of audio
- **Speed**: Ultra-fast (<1s for 1-minute audio)
- **Best For**: Real-time, frequent transcription

### OpenAI Whisper
- **Cost**: $0.006 per minute (~$0.36 per hour)
- **Speed**: Fast (<2s for 1-minute audio)
- **Best For**: High-quality transcription, fallback

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
   - Solution: Chunk into 10-minute segments, transcribe separately
   
3. **Low Audio Quality**
   - Solution: Apply noise reduction, warn user if confidence is low
   
4. **Language Detection Failure**
   - Solution: Prompt user to specify language explicitly

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
- **Temporary Files**: Delete after transcription

## Integration Points

### CLI
- `cyberagent transcribe <file>`
- `cyberagent listen [--stream]`

### Inbox
- Auto-transcribe voice messages from messaging platforms
- Display transcript alongside audio in inbox

### Messaging Channels
- Telegram: Receive voice messages, auto-transcribe

### Agent Skills
Agents can request transcription via skill:
```python
# In agent skill
audio_path = "path/to/recording.wav"
transcript = stt.transcribe(audio_path)
agent.process_command(transcript)
```

## Future Enhancements
- **Emotion Detection**: Detect tone, sentiment in voice
- **Multi-Language Switching**: Auto-switch between languages in same audio

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
6. Test fallback by disabling Groq, verify OpenAI is used
7. Test long audio (>10 minutes), verify chunking works

## Notes For Resuming Later
- Current STT exists only in the Telegram flow and bypasses the inbox. There is no shared STT module for CLI/audio files yet.
- Telegram STT uses Groq/OpenAI endpoints directly via `requests` and returns plain text (no timestamps/segments), which differs from the richer output assumed in this PRD.
- Long audio is rejected by duration in Telegram (`TELEGRAM_STT_MAX_DURATION`) instead of chunked.
- There is no CLI surface for STT today, even though the PRD still references it.
- Surprising: Telegram STT config already supports provider fallback and language selection via env, but none of that is exposed in a CLI or config file.

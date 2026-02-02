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

### 1. Voice Commands via CLI
```bash
# Record audio and transcribe
cyberagent listen --duration 5s

# Transcribe audio file
cyberagent transcribe path/to/audio.wav

# Real-time transcription
cyberagent listen --stream
```

### 2. Voice Messages in Inbox
Users send voice messages via messaging platforms (Telegram, WhatsApp):
1. Audio file arrives at System4 inbox
2. STT transcribes the audio
3. Transcribed text is processed as a message
4. Agent responds via text or voice (TTS)

### 3. Meeting Transcripts
```bash
# Transcribe a meeting recording
cyberagent transcribe meeting.mp3 --speaker-diarization

# Output: Timestamped transcript with speaker labels
[00:00:12] Speaker 1: "Let's discuss the backend architecture..."
[00:00:18] Speaker 2: "I think we should use microservices..."
```

### 4. Voice-Activated Agents
Agents listen for wake words and activate on voice commands:
```
User: "Hey CyberAgent, deploy the staging environment"
Agent: *transcribes* → *processes command* → *executes deployment*
```

## Architecture

### STT Pipeline
```
Audio Input → Preprocessing → Transcription Model → Post-Processing → Text Output
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
- **Normalization**: Adjust volume levels
- **Noise Reduction**: Remove background noise
- **Format Conversion**: Convert to model-compatible format (e.g., 16kHz WAV)
- **Chunking**: Split long audio into manageable segments

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

**Local Whisper (Optional)**
- Runs locally via `whisper` Python package
- Free but slower and resource-intensive
- Useful for privacy-sensitive contexts

#### 4. Post-Processing
- **Punctuation & Capitalization**: Auto-insert based on context
- **Speaker Diarization**: Identify who said what (optional)
- **Timestamp Injection**: Add timestamps for long transcripts
- **Language Detection**: Auto-detect input language

### Configuration
```yaml
stt:
  provider: "groq"  # groq | openai | local
  model: "whisper-large-v3-turbo"
  language: "auto"  # auto-detect or specify (e.g., "en", "es", "de")
  enable_timestamps: true
  enable_speaker_diarization: false
  preprocessing:
    noise_reduction: true
    normalize_volume: true
  fallback_provider: "openai"
  max_audio_duration_seconds: 600  # 10 minutes
```

## Implementation

### Phase 1: File-Based Transcription
- **Deliverable**: CLI command to transcribe audio files
- **Components**:
  - Audio file reader
  - Groq Whisper API integration
  - Text output to CLI

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

### Phase 3: Real-Time Streaming (Optional)
- **Deliverable**: Live transcription from microphone
- **Challenges**: Requires chunking and stateful processing
- **Use Case**: Voice-activated agents, live meetings

```python
# Pseudo-code for streaming
def stream_transcribe(microphone_stream):
    buffer = AudioBuffer(chunk_size=5s)
    
    for chunk in microphone_stream:
        buffer.append(chunk)
        
        if buffer.is_full():
            transcript = transcribe_chunk(buffer.get_audio())
            yield transcript
            buffer.clear()
```

### Phase 4: Speaker Diarization
- **Deliverable**: Multi-speaker transcripts with labels
- **Provider**: Pyannote.audio (open-source) or AssemblyAI
- **Output**:
```json
{
  "segments": [
    {"start": 0.0, "end": 5.2, "speaker": "SPEAKER_1", "text": "Hello everyone"},
    {"start": 5.5, "end": 9.1, "speaker": "SPEAKER_2", "text": "Hi, thanks for joining"}
  ]
}
```

## CLI Commands

### Transcribe Audio File
```bash
cyberagent transcribe <file_path> [OPTIONS]

Options:
  --provider      STT provider (groq|openai|local) [default: groq]
  --model         Model name [default: whisper-large-v3-turbo]
  --language      Language code (auto|en|es|de|...) [default: auto]
  --timestamps    Include timestamps in output
  --diarization   Enable speaker diarization
  --output        Output file path (optional)
```

**Example:**
```bash
$ cyberagent transcribe meeting.mp3 --timestamps --diarization

Transcribing meeting.mp3 (8m 34s)...
Provider: groq/whisper-large-v3-turbo
Language: en (auto-detected)

[00:00:03] SPEAKER_1: "Let's start with the quarterly review."
[00:00:12] SPEAKER_2: "Sounds good. Revenue is up 15% this quarter."
[00:00:21] SPEAKER_1: "That's great news. What about user growth?"
...

Transcript saved to: meeting_transcript_2026-02-02.txt
```

### Live Transcription
```bash
cyberagent listen [OPTIONS]

Options:
  --duration      Recording duration (e.g., 5s, 1m) [default: until Enter]
  --stream        Enable real-time streaming transcription
  --command       Execute transcribed text as a command
```

**Example:**
```bash
$ cyberagent listen --duration 10s

🎤 Recording... (10s)

Transcription:
"Check the status of the backend team and send me a summary."

Execute as command? (y/n): y

Executing: cyberagent team status backend_team
...
```

## Inbox Integration

### Automatic Transcription
When a voice message arrives:
1. **Detection**: System4 detects audio attachment
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
After processing a voice message, agent can respond with TTS:
```
User: 🎤 "What's the status of the deployment?"
Agent: 🔊 "The deployment is 80% complete. ETA: 5 minutes."
```

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
        logger.error(f"OpenAI failed: {e}, falling back to local Whisper")
        return local_whisper_transcribe(audio_path)
```

## Security & Privacy

### Audio Storage
- **Temporary Files**: Delete after transcription (unless explicitly saved)
- **Retention Policy**: Audio files auto-delete after 30 days
- **Encryption**: Encrypt audio files at rest

### Transcript Logging
- **Audit Trail**: Log who transcribed what and when
- **Redaction**: Support PII redaction for sensitive transcripts

## Integration Points

### CLI
- `cyberagent transcribe <file>`
- `cyberagent listen [--stream]`

### System4 Inbox
- Auto-transcribe voice messages from messaging platforms
- Display transcript alongside audio in inbox

### Messaging Channels
- Telegram: Receive voice messages, auto-transcribe
- WhatsApp: Receive voice notes, auto-transcribe
- Phone Calls (Future): Transcribe live calls via Twilio

### Agent Skills
Agents can request transcription via skill:
```python
# In agent skill
audio_path = "path/to/recording.wav"
transcript = stt.transcribe(audio_path)
agent.process_command(transcript)
```

## Success Metrics
1. **Transcription Accuracy**: >95% word error rate (WER)
2. **Latency**: <2s for 1-minute audio
3. **Cost**: <$10/month for typical usage (50 hours/month)
4. **Adoption**: 30% of messages via voice within 3 months

## Future Enhancements
- **Wake Word Detection**: "Hey CyberAgent" activation
- **Emotion Detection**: Detect tone, sentiment in voice
- **Multi-Language Switching**: Auto-switch between languages in same audio
- **Voice Commands**: Direct voice control of CLI commands
- **Live Meeting Transcripts**: Real-time transcription for team calls

## References
- [Groq Whisper API](https://console.groq.com/docs/speech-text)
- [OpenAI Whisper](https://platform.openai.com/docs/guides/speech-to-text)
- [Whisper GitHub](https://github.com/openai/whisper)
- [Pyannote Audio (Speaker Diarization)](https://github.com/pyannote/pyannote-audio)

## Related Features
- TTS (Text-to-Speech) for voice replies
- Agent Inbox for message routing
- Messaging Channels (Telegram, WhatsApp)
- CLI for voice command execution

## How to Test
1. Record a 30-second voice message
2. Run `cyberagent transcribe test.wav`
3. Verify accuracy of transcription
4. Send voice message via Telegram
5. Verify auto-transcription in inbox
6. Test fallback by disabling Groq, verify OpenAI is used
7. Test long audio (>10 minutes), verify chunking works

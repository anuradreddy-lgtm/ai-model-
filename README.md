# ⚡ JARVIS AI — Open-Source Windows Desktop Assistant

**JARVIS** is a voice-enabled, local personal AI desktop assistant built specifically for Windows. It runs completely offline using local open-source language models, neural audio processing, high-accuracy speech recognition (`faster-whisper`), natural speech synthesis (SAPI5), and safe allowlisted Windows system tools.

---

## 🌟 Capabilities & Features

### 1. High-Accuracy Local Speech-to-Text (STT)
- **100% Offline & Private**: Powered by `faster-whisper` running locally in C++ with `int8` quantization on CPU. Zero audio or transcripts ever leave your PC.
- **Hardware-Matched Audio Capture**: Native querying of Windows audio devices (e.g. 44.1 kHz / 48 kHz stereo) with in-memory stereo-to-mono downmix and numpy linear resampling to 16 kHz.
- **Voice Activity Detection (VAD)**: Energy-based silence trimming with pre-speech and post-speech frame padding to prevent word clipping while rejecting background noise and clicks.
- **Microphone Selection**: Enumerate and select from all installed Windows audio input devices in Settings (MME, DirectSound, WASAPI, WDM-KS).
- **Anti-Hallucination Guardrails**: Filters silence, low-confidence noise, and repetitive tokens (`no_speech_threshold=0.55`, `condition_on_previous_text=False`).
- **Configurable Models**: Supports `base.en`, `tiny.en`, `small.en`, and multilingual `base`.

### 2. Natural Text-to-Speech (TTS) & Barge-In
- **Calm, Confident Delivery**: Configured with `Microsoft David Desktop` (classic masculine JARVIS persona) at a natural 185 WPM pace, with support for `Microsoft Zira` and custom voices.
- **Abbreviation & Tech Term Expansion**: Natural spoken translation of technical tokens (`CPU` → "C.P.U.", `RAM` → "R.A.M.", `GB` → "gigabytes", `WPM` → "words per minute", `vs` → "versus", `e.g.` → "for example", `Ollama` → "Oll-ahma", `%` → "percent").
- **Sentence Chunking**: Splits long model paragraphs into natural sentence-sized units with organic punctuation pauses.
- **Instant Barge-In**: Clicking **Start Listening** or **Stop** immediately halts speech synthesis and releases audio threads.

### 3. Local LLM Intelligence
- **Local Ollama Inference**: Connects directly to Ollama at `http://localhost:11434/api/chat`.
- **Default High-Performance Model**: Verified with `gemma4:e2b` (with automatic fallback to `qwen2.5:3b` or other installed local models).
- **Tool-Call Feedback Loop**: Automatically executes approved tools, feeds structured system results back to the model, and outputs a clean spoken response without internal action blocks.
- **Non-Blocking UI**: Asynchronous worker threads keep the UI fluid and 30 FPS responsive during model generation.

### 4. Futuristic Dark Desktop Interface
- **PySide6 (Qt 6)** with dark cyan and electric blue aesthetics.
- **Central JARVIS Reactor Orb**: Multilayer glowing core with counter-rotating tech rings responding to audio energy and states.
- **Dynamic Waveform Visualizer**: 36-band animated frequency spectrum reflecting microphone input and playback.
- **Full Assistant States**: `Sleeping`, `Listening`, `Transcribing` (`#FF9100`), `Recognized` (`#38BDF8`), `Thinking`, `Speaking`, `Executing`, and `Error`.
- **Voice & Speech Settings Tab**: Live microphone test, voice output test, device switcher, model picker, and 1-click comprehensive voice diagnostics report.

### 5. Safe Windows Tool Registry
- **Strict Validation**: All tool arguments validated independently of the LLM.
- **Zero Shell Strings**: Direct executable execution (`subprocess.Popen([exe])`, never `shell=True`).
- **Date & Time**: `get_current_time`.
- **Application Launcher**: Notepad, Calculator, Paint, Explorer, Task Manager (with strict allowlist).
- **Browser Opener**: Safe opening of allowlisted websites in the default browser.
- **Hardware Diagnostics**: Real-time CPU, RAM utilization, and battery status.
- **Folder Search**: Safe filename search with depth constraints.
- **Notes Manager**: Persistent note taking in `%LOCALAPPDATA%\JARVIS\notes`.
- **Persistent SQLite Memory**: Stores user facts and conversation history locally in WAL mode.

---

## 🏗️ Architecture & Project Structure

```text
d:\open source ai\
├── jarvis/
│   ├── config.py                 # Configuration dataclasses (LLM, Voice, Hardware, Safety)
│   ├── core/
│   │   ├── events.py             # Qt event bus signals
│   │   └── state.py              # AssistantState enum and styling definitions
│   ├── llm/
│   │   ├── ollama_client.py      # Resilient Ollama client with token streaming & cancellation
│   │   └── prompts.py            # System prompts, persona directives, and tool schemas
│   ├── conversation/
│   │   └── manager.py            # Turn bounding, balanced-JSON action parser, and tool loop
│   ├── tools/
│   │   ├── registry.py           # Tool decorator, parameter type checking, execution allowlist
│   │   ├── system_tools.py       # Date/time and hardware statistics (CPU, RAM, Battery)
│   │   ├── app_launcher.py       # Safe subprocess launcher for allowlisted apps
│   │   ├── browser_tools.py      # Validated URL opening in default web browser
│   │   ├── filesystem_tools.py   # Bounded filename search inside user folders
│   │   ├── notes_tools.py        # Read/write notes in dedicated %LOCALAPPDATA%/JARVIS/notes
│   │   └── memory_tools.py       # Tools to remember and recall user facts
│   ├── storage/
│   │   ├── db.py                 # SQLite database schema, connections, and WAL mode
│   │   └── memory.py             # Conversation logs and user facts CRUD operations
│   ├── voice/
│   │   ├── audio_capture.py      # Native hardware audio capture, resampling, VAD, bounded queues
│   │   ├── stt.py                # Local faster-whisper STT with anti-hallucination guardrails
│   │   ├── tts.py                # Asynchronous sentence-chunked TTS with abbreviation expansion
│   │   ├── diagnostics.py        # Hardware enumeration, mic tester, and full diagnostic report
│   │   └── wake_word.py          # Wake-word adapter with graceful fallback to push-to-talk
│   ├── ui/
│   │   ├── theme.py              # Futuristic dark theme stylesheet (QSS)
│   │   ├── main_window.py        # Main window assembling visualizer, chat view, and controls
│   │   └── widgets/
│   │       ├── visualizer.py     # Central animated pulsing reactor orb & dynamic waveform
│   │       ├── chat_view.py      # Chat message bubbles with real-time streaming
│   │       ├── status_bar.py     # State badge, Ollama indicator, mic indicator, mute toggle
│   │       └── settings_dialog.py# Voice settings, LLM config, memory viewer, and diagnostics
│   └── utils/
│       └── logger.py             # Console and rotating file logger (%LOCALAPPDATA%/JARVIS/logs)
├── tests/
│   ├── test_config.py            # Configuration paths, state colors, security rules
│   ├── test_ollama.py            # Ollama client, health check, mock streaming
│   ├── test_conversation.py      # History bounding, action parser, state transitions
│   ├── test_tools.py             # Tool parameter validation, allowlists, safe subprocesses
│   ├── test_voice.py             # Audio capture, resampling, VAD, STT, TTS cleaning & splitting
│   ├── test_voice_diagnostics.py # Device enumeration, capture testing, diagnostic report
│   ├── test_memory.py            # SQLite schema, message logging, facts CRUD
│   └── test_ui.py                # Status bar, bubbles, visualizer, MainWindow layout
├── requirements.txt              # Production dependencies
├── jarvis.spec                   # PyInstaller standalone build specification
├── run.py                        # Entry point launcher
└── README.md
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites
- **Windows 10 or 11 (64-bit)**
- **Python 3.11+ / Python 3.14**
- **Ollama for Windows**: Download from [ollama.com](https://ollama.com).
  Ensure your target model is running:
  ```powershell
  ollama pull gemma4:e2b
  ```

### 2. Installation
Navigate to the project directory:
```powershell
cd "d:\open source ai"
py -m pip install -r requirements.txt
```

### 3. Run Automated Tests
Execute the full test suite (44 unit & integration tests):
```powershell
py -m pytest -v
```

### 4. Test Model Connection
Verify your local Ollama instance and Gemma 4 model:
```powershell
py run.py --test-connection
```

### 5. Launch JARVIS Desktop Application
```powershell
py run.py
```

---

## 🎮 How to Use JARVIS

### Push-to-Talk Voice Interaction
1. Click **🎤 Start Listening**. The button turns red (**🔴 Recording... (Click to Finish)**), and the orb glows bright cyan (`Listening`).
2. Speak your command into your microphone naturally.
3. Click the button again to finish speaking.
4. JARVIS immediately transitions to **Transcribing** (Amber `#FF9100`) as `faster-whisper` decodes the audio in memory.
5. The recognized text appears in chat, and the orb pulses purple (`Thinking`) while `gemma4:e2b` generates the answer.
6. JARVIS responds aloud with natural, sentence-paced speech (`Speaking`).

### Instant Barge-In
- If JARVIS is speaking and you click **Start Listening** or **Stop**, speech playback halts instantly so you can immediately give a new instruction.

### Typed Chat
You can also type your command directly into the input bar and press **Enter**:
- *"What time is it?"*
- *"Check my CPU and RAM usage"*
- *"Open calculator"*
- *"Open notepad"*
- *"Open wikipedia"*
- *"Remember that my name is Anurag"*
- *"What is my name?"*

### Voice & Hardware Settings
Open **⚙ Settings** > **Voice & Speech**:
- Select your preferred physical microphone from the enumerated device list.
- Click **🎤 Test Selected Microphone** to verify sample rates and RMS levels.
- Choose your Whisper model (`base.en` recommended, `tiny.en` for lightweight CPU).
- Toggle Voice Activity Detection (VAD).
- Select your preferred TTS voice (`Microsoft David` / `Microsoft Zira`).
- Adjust speech rate (WPM) and volume.
- Click **🔍 Run Full Voice Diagnostics** to see an instant hardware and model health report.

---

## 🛡️ Security & Privacy Disclosures

- **100% Offline by Default**: LLM inference, speech-to-text recognition, text-to-speech, and database operations execute locally. No cloud endpoints, no hidden telemetry.
- **Subprocess Security**: All tool execution uses strict executable argument lists (e.g. `['notepad.exe']`). Arbitrary command strings (`shell=True`, `cmd /c`) are strictly prohibited.
- **In-Memory Audio**: Audio is streamed in-memory via numpy float32 arrays and is never written continuously to disk.
- **Microphone Release**: The audio stream is cleanly closed and hardware released whenever listening stops.

\# J.A.R.V.I.S — Personal AI Assistant



A fully voice-controlled AI assistant built in Python, running a local LLM (LLaMA 3.2 via Ollama). No cloud. No API keys. Fully private.



Inspired by Iron Man's Jarvis — sarcastic, dry wit, always calls you Sir.



\---



\## Demo



> "Jarvis, what's the weather?"  

> \*"Current weather in Chennai is 34°C and sunny Sir. Dress accordingly. Or don't. Your choice."\*



> "Jarvis, remember I have an exam tomorrow"  

> \*"Noted Sir. Filed away in my impeccable memory."\*



\---



\## Features



\### ✅ Completed Levels



| Level | Feature | Status |

|-------|---------|--------|

| 1 | Time-aware personality — morning/evening/night greetings | ✅ Done |

| 2 | Daily briefing — weather, news, battery on startup | ✅ Done |

| 3 | Full laptop control — volume, brightness, WiFi, screenshots, app launch/kill | ✅ Done |

| 4 | AI brain — powered by LLaMA 3.2 via Ollama, dry wit, sarcastic personality | ✅ Done |

| 5 | Persistent memory — facts, preferences, habits, conversation history across sessions | ✅ Done |



\### 🔜 Upcoming

\- Level 6 — Proactive Jarvis (reminders, suggestions without being asked)

\- Level 7 — Phone + laptop as one (WhatsApp call handling, cross-device control)

\- Level 8 — Face recognition (auto wake-up when you sit down)

\- Level 9 — Own AI server (self-hosted, no Ollama dependency)



\---



\## Tech Stack



\- \*\*Python 3.11\*\*

\- \*\*Ollama + LLaMA 3.2\*\* — local LLM, runs fully offline

\- \*\*SpeechRecognition + Google STT\*\* — voice input

\- \*\*pyttsx3\*\* — text-to-speech output

\- \*\*Flask + Flask-SocketIO\*\* — web dashboard

\- \*\*pywebview\*\* — animated desktop UI window

\- \*\*PyAutoGUI\*\* — system control (volume, screenshots)

\- \*\*screen-brightness-control\*\* — brightness control

\- \*\*psutil\*\* — battery monitoring

\- \*\*Threading + Locks\*\* — multi-threaded architecture



\---



\## Project Structure



```

Jarvis/

├── jarvis.py           # Main assistant — all logic lives here

├── jarvis\_face.html    # Animated UI (canvas-based, Iron Man HUD style)

├── app.py              # Flask web dashboard

├── memory.json         # Persistent memory (auto-created on first run)

├── start\_jarvis.bat    # Windows launcher

├── requirements.txt    # Python dependencies

└── tests/

&#x20;   ├── test.py         # TTS test

&#x20;   ├── test2.py        # Microphone test

&#x20;   ├── mictest.py      # Mic sensitivity test

&#x20;   ├── apitest.py      # Weather + news API test

&#x20;   ├── test\_flask.py   # Flask test

&#x20;   ├── watest.py       # Window detection test

&#x20;   └── calltest.py     # WhatsApp call detection test

```



\---



\## Setup \& Installation



\### 1. Install Ollama and pull the model

```bash

\# Download Ollama from https://ollama.com

ollama pull llama3.2

```



\### 2. Clone the repo

```bash

git clone https://github.com/YOUR\_USERNAME/jarvis.git

cd jarvis

```



\### 3. Install Python dependencies

```bash

pip install -r requirements.txt

```



\### 4. Update the memory file path in jarvis.py

Open `jarvis.py` and change line 21 to your actual path:

```python

MEMORY\_FILE = "C:\\\\Users\\\\YOUR\_NAME\\\\path\\\\to\\\\Jarvis\\\\memory.json"

```



\### 5. Run Jarvis

```bash

python jarvis.py

\# or double-click start\_jarvis.bat on Windows

```



\---



\## Voice Commands



| Say | What happens |

|-----|-------------|

| `Jarvis` | Wake word — Jarvis listens for your command |

| `Jarvis, remember \[anything]` | Stores a fact in memory |

| `Jarvis, what do you remember` | Recalls stored facts |

| `Jarvis, what are my preferences` | Lists learned preferences |

| `Jarvis, what are my habits` | Shows your usage patterns |

| `Jarvis, briefing` | Full morning/evening briefing |

| `Jarvis, open YouTube` | Opens YouTube, asks what to search |

| `Jarvis, volume up/down` | Adjusts system volume |

| `Jarvis, brightness up/down` | Adjusts screen brightness |

| `Jarvis, take screenshot` | Screenshots to desktop |

| `Jarvis, WiFi on/off` | Toggles WiFi |

| `Jarvis, open \[app name]` | Launches any installed app |

| `Jarvis, close \[app name]` | Kills any running process |

| `Jarvis, lock` | Locks the screen |

| `Jarvis, go home` | Shuts down Jarvis |

| Anything else | Goes to LLaMA 3.2 for an answer |



\---



\## Memory System (Level 5)



Jarvis remembers across sessions using a 5-layer memory stored in `memory.json`:



\- \*\*Facts\*\* — things you manually tell it (`Jarvis, remember I prefer dark mode`)

\- \*\*Preferences\*\* — auto-learned from phrases like `I like lofi music`

\- \*\*Habits\*\* — silently tracks what you do most (open YouTube 12x, check weather 8x)

\- \*\*Conversations\*\* — stores last 20 exchanges, fed into the AI prompt for context

\- \*\*Sessions\*\* — counts how many times Jarvis has been started



All memory is used automatically in the AI prompt so responses get more personalised over time.



\---



\## Requirements



```

SpeechRecognition

pyttsx3

pyaudio

psutil

requests

flask

flask-socketio

pywebview

pyautogui

screen-brightness-control

ollama

pygetwindow

```



\---



\## Known Issues / Notes



\- Requires Windows (uses `netsh`, `rundll32`, Windows volume keys)

\- Microphone must be set as default input device

\- Ollama must be running in background before starting Jarvis

\- `memory.json` path is hardcoded — update it to your system path



\---



\## About



Built by \*\*Jaswanth Kumar Kolapalli\*\* — CS undergrad (AI \& ML) at VIT Vellore.



This is a passion project. Every bug I fixed taught me something the tutorials never would.



\*"The most sophisticated AI assistant in Chennai. I might add."\*


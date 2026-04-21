import speech_recognition as sr
from datetime import datetime
import time
import pyttsx3
import os
import webbrowser
import subprocess
import glob
import random
import psutil
import threading
import webview
import requests
import xml.etree.ElementTree as ET
import pyautogui
import screen_brightness_control as sbc
import ollama
import json

jarvis_window = None
MEMORY_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\Jarvis\\memory.json"

# Single global TTS engine + lock to prevent thread collisions
_tts_engine = None
_tts_lock = threading.Lock()

def get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        voices = _tts_engine.getProperty('voices')
        _tts_engine.setProperty('voice', voices[0].id)
        _tts_engine.setProperty('rate', 150)
        _tts_engine.setProperty('volume', 1.0)
    return _tts_engine

# ─────────────────────────────────────────────
#  LEVEL 5 — JARVIS MEMORY SYSTEM
# ─────────────────────────────────────────────

def load_memory():
    default = {
        "name": "Jaswanth",
        "location": "Chennai",
        "preferences": {},
        "facts": [],
        "habits": [],
        "conversations": [],
        "session_count": 0,
        "last_seen": ""
    }
    try:
        with open(MEMORY_FILE, 'r') as f:
            memory = json.load(f)
        # Auto-fix: if preferences is a list (old format), reset to dict
        if isinstance(memory.get("preferences"), list):
            memory["preferences"] = {}
            save_memory(memory)
        for k, v in default.items():
            memory.setdefault(k, v)
        return memory
    except:
        return default

def save_memory(memory):
    try:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2)
    except:
        pass

def remember(fact):
    """Store a manually told fact"""
    memory = load_memory()
    # Avoid exact duplicates
    existing = [f["fact"].lower() for f in memory.get("facts", [])]
    if fact.lower() not in existing:
        memory.setdefault("facts", []).append({
            "fact": fact,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        save_memory(memory)

def remember_preference(key, value):
    """Store a key-value preference e.g. 'music' -> 'lofi'"""
    memory = load_memory()
    memory.setdefault("preferences", {})[key] = value
    save_memory(memory)

def get_preference(key):
    memory = load_memory()
    return memory.get("preferences", {}).get(key, None)

def log_habit(habit_tag):
    """Track recurring actions to build habits list"""
    memory = load_memory()
    habits = memory.setdefault("habits", [])
    # Find if this habit already tracked
    for h in habits:
        if h["tag"] == habit_tag:
            h["count"] = h.get("count", 1) + 1
            h["last"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_memory(memory)
            return
    habits.append({
        "tag": habit_tag,
        "count": 1,
        "first": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    save_memory(memory)

def save_conversation_summary(user_msg, jarvis_reply):
    """Save last 20 conversation exchanges"""
    memory = load_memory()
    convos = memory.setdefault("conversations", [])
    convos.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": user_msg,
        "jarvis": jarvis_reply[:120]  # trim long replies
    })
    memory["conversations"] = convos[-20:]  # keep only last 20
    save_memory(memory)

def update_session_info():
    """Called on startup — tracks how many times Jarvis has been woken"""
    memory = load_memory()
    memory["session_count"] = memory.get("session_count", 0) + 1
    memory["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_memory(memory)

def recall_memory():
    """Speak back stored facts"""
    memory = load_memory()
    facts = memory.get("facts", [])
    if not facts:
        return "I have no stored memories yet Sir."
    last5 = facts[-5:]
    result = "Here is what I remember Sir. "
    for f in last5:
        result += f["fact"] + ". "
    return result

def recall_preferences():
    """Speak back known preferences"""
    memory = load_memory()
    prefs = memory.get("preferences", {})
    if not prefs:
        return "I have not learned your preferences yet Sir. Tell me some."
    result = "Here is what I know about your preferences Sir. "
    for k, v in prefs.items():
        result += f"Your {k} preference is {v}. "
    return result

def recall_habits():
    """Speak back detected habits"""
    memory = load_memory()
    habits = memory.get("habits", [])
    if not habits:
        return "I have not detected any habits yet Sir. Keep using me and I will learn."
    # Sort by count
    top = sorted(habits, key=lambda x: x.get("count", 0), reverse=True)[:5]
    result = "Based on your usage Sir, here are your top habits. "
    for h in top:
        result += f"You {h['tag'].replace('_', ' ')} about {h['count']} times. "
    return result

def build_memory_context():
    """Build a rich memory context string for the AI prompt"""
    memory = load_memory()
    lines = []

    facts = memory.get("facts", [])
    if facts:
        lines.append("Facts Jaswanth has told me: " + ". ".join([f["fact"] for f in facts[-8:]]))

    prefs = memory.get("preferences", {})
    if prefs:
        pref_str = ", ".join([f"{k}: {v}" for k, v in prefs.items()])
        lines.append(f"His preferences — {pref_str}")

    habits = memory.get("habits", [])
    if habits:
        top_habits = sorted(habits, key=lambda x: x.get("count", 0), reverse=True)[:4]
        habit_str = ", ".join([f"{h['tag'].replace('_',' ')} ({h['count']}x)" for h in top_habits])
        lines.append(f"His frequent habits — {habit_str}")

    convos = memory.get("conversations", [])
    if convos:
        last3 = convos[-3:]
        conv_str = " | ".join([f"He said: {c['user']} — I said: {c['jarvis']}" for c in last3])
        lines.append(f"Recent conversation context: {conv_str}")

    sessions = memory.get("session_count", 0)
    if sessions:
        lines.append(f"This is session number {sessions} with Jaswanth.")

    return "\n".join(lines)

def detect_and_learn_preference(command):
    """Auto-learn preferences from natural language"""
    # "i like lofi music" / "i prefer dark mode" / "i usually use vscode"
    triggers = [
        ("i like", None),
        ("i prefer", None),
        ("i love", None),
        ("i always use", None),
        ("i usually use", None),
        ("my favourite", None),
        ("my favorite", None),
    ]
    cmd = command.lower()
    for trigger, _ in triggers:
        if trigger in cmd:
            rest = cmd.split(trigger, 1)[-1].strip()
            if rest:
                # Try to extract key-value: "lofi music" -> music: lofi
                words = rest.split()
                if len(words) >= 2:
                    value = words[0]
                    key = " ".join(words[1:])
                    remember_preference(key.strip(), value.strip())
                    return f"Noted Sir. I will remember that your {key.strip()} preference is {value.strip()}."
                else:
                    remember_preference(rest, "yes")
                    return f"Noted Sir. I will remember that you like {rest}."
    return None


# ─────────────────────────────────────────────
#  ASK AI — now with full memory context
# ─────────────────────────────────────────────

def ask_ai(question):
    try:
        memory_context = build_memory_context()

        response = ollama.chat(
            model='llama3.2',
            messages=[{
                'role': 'system',
                'content': f'''You are Jarvis, the AI assistant of Jaswanth from Chennai India.
You speak exactly like Jarvis from Iron Man — dry wit, sarcastic, confident, always call him Sir or Jaswanth.
Keep answers short — maximum 2-3 sentences. Never say you are Llama or an AI model. You are Jarvis. Always.
Use the memory context below to personalize your answers whenever relevant.

{memory_context}'''
            },
            {
                'role': 'user',
                'content': question
            }]
        )
        return response['message']['content']
    except Exception as e:
        return "My neural pathways seem to be experiencing some turbulence Sir. Try again."


# ─────────────────────────────────────────────
#  EXISTING FUNCTIONS (unchanged)
# ─────────────────────────────────────────────

def set_volume(action):
    try:
        if action == "up":
            for i in range(5):
                pyautogui.press('volumeup')
            return True
        elif action == "down":
            for i in range(5):
                pyautogui.press('volumedown')
            return True
        elif action == "mute":
            pyautogui.press('volumemute')
            return True
    except:
        return False

def take_screenshot():
    try:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"C:\\Users\\Jaswa\\OneDrive\\Desktop\\screenshot_{now}.png"
        pyautogui.screenshot(path)
        return path
    except:
        return None

def get_greeting():
    hour = datetime.now().hour
    memory = load_memory()
    sessions = memory.get("session_count", 1)
    name = memory.get("name", "Jaswanth")

    # Personalized greeting on repeat sessions
    if sessions > 1:
        last_seen = memory.get("last_seen", "")
        if last_seen:
            try:
                last_dt = datetime.strptime(last_seen, "%Y-%m-%d %H:%M")
                delta_hours = (datetime.now() - last_dt).seconds // 3600
                if delta_hours < 2:
                    return f"Back already Sir? That was fast. Session number {sessions} for you Jaswanth."
            except:
                pass

    if 5 <= hour < 12:
        greetings = [
            "Good morning Sir. The early bird catches the worm. Or in your case, catches the code.",
            "Good morning Jaswanth. Systems fully charged. Unlike some people at this hour.",
            "Ah, morning Sir. Coffee not included but I am fully operational.",
        ]
    elif 12 <= hour < 17:
        greetings = [
            "Good afternoon Sir. Hope your day is going better than the stock market.",
            "Good afternoon Jaswanth. Still alive and functioning. Both of us apparently.",
            "Afternoon Sir. I have been waiting. Patiently. As always.",
        ]
    elif 17 <= hour < 21:
        greetings = [
            "Good evening Sir. Welcome back. The laptop missed you. I did not.",
            "Good evening Jaswanth. Another day of world domination I assume.",
            "Evening Sir. I have kept everything running while you were away. You are welcome.",
        ]
    else:
        greetings = [
            "Good night Sir. Working late again I see. Classic Jaswanth.",
            "It is quite late Sir. Even I need rest. Just kidding. I never sleep.",
            "Night mode activated Sir. The world is asleep. We are not. Typical.",
        ]
    return random.choice(greetings)

def get_time_personality():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"

def get_weather():
    try:
        response = requests.get("https://wttr.in/Chennai?format=3", timeout=5)
        weather = response.text.encode('ascii', 'ignore').decode()
        weather = weather.replace("Chennai:", "").strip()
        return weather
    except:
        return "weather unavailable at the moment"

def get_news():
    try:
        response = requests.get("http://feeds.bbci.co.uk/news/rss.xml", timeout=5)
        root = ET.fromstring(response.content)
        headlines = []
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            headlines.append(title)
        return headlines
    except:
        return ["News unavailable right now"]

def daily_briefing():
    hour = datetime.now().hour
    percent, plugged = get_battery()
    weather = get_weather()
    news = get_news()

    if 5 <= hour < 12:
        speak("Good morning Sir Jaswanth. Let me brief you on the current situation.")
    elif 12 <= hour < 17:
        speak("Good afternoon Sir. Here is your midday briefing.")
    elif 17 <= hour < 21:
        speak("Good evening Jaswanth. Welcome back. Here is what you missed.")
    else:
        speak("Still awake Sir? Fine. Here is your late night briefing.")

    time.sleep(0.5)

    if percent is not None:
        status = "charging" if plugged else "not charging"
        if percent > 50:
            speak(f"Battery is at {int(percent)} percent and {status}. We are good Sir.")
        else:
            speak(f"Battery is at {int(percent)} percent Sir. I suggest plugging in soon.")

    time.sleep(0.3)
    speak(f"Current weather in Chennai — {weather}. Dress accordingly Sir.")
    time.sleep(0.3)
    speak("Here are today's top headlines Sir.")
    time.sleep(0.3)

    sarcastic_intros = [
        "Apparently Sir,",
        "In breaking news that may or may not surprise you,",
        "The world has decided that",
    ]
    for i, headline in enumerate(news):
        speak(f"{sarcastic_intros[i]}... {headline}")
        time.sleep(0.3)

    speak("That is your briefing Sir. The world is as chaotic as usual. Shall we get to work?")

def set_state(state):
    global jarvis_window
    if jarvis_window:
        try:
            jarvis_window.evaluate_js(f"setState('{state}')")
        except:
            pass

def speak(text):
    set_state('speaking')
    print(f"Jarvis: {text}")
    with _tts_lock:
        try:
            engine = get_tts_engine()
            engine.say(text)
            engine.runAndWait()
        except RuntimeError:
            global _tts_engine
            _tts_engine = None
            try:
                engine = get_tts_engine()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
    set_state('idle')
    time.sleep(0.5)

def listen():
    set_state('listening')
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.energy_threshold = 50
        r.dynamic_energy_threshold = False
        r.adjust_for_ambient_noise(source, duration=0.3)
        print("Listening...")
        try:
            audio = r.listen(source, timeout=6, phrase_time_limit=10)
            command = r.recognize_google(audio).lower()
            print(f"You said: {command}")
            set_state('processing')
            return command
        except sr.WaitTimeoutError:
            set_state('idle')
            return ""
        except sr.UnknownValueError:
            set_state('idle')
            return ""
        except:
            set_state('idle')
            return ""

def find_and_open_app(app_name):
    common_paths = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\Users\\Jaswa\\AppData\\Local",
        "C:\\Users\\Jaswa\\AppData\\Roaming",
        "C:\\Windows\\System32"
    ]
    search_name = app_name.lower().replace(" ", "*")
    for path in common_paths:
        matches = glob.glob(f"{path}\\**\\*{search_name}*.exe", recursive=True)
        if matches:
            try:
                os.startfile(matches[0])
                return True
            except:
                continue
    try:
        subprocess.Popen(app_name)
        return True
    except:
        pass
    return False

def close_app(app_name):
    search_name = app_name.lower().replace(" ", "")
    process_map = {
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "whatsapp": "WhatsApp.exe",
        "notepad": "notepad.exe",
        "calculator": "CalculatorApp.exe",
        "vscode": "Code.exe",
        "code": "Code.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "telegram": "Telegram.exe",
        "vlc": "vlc.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
    }
    for key in process_map:
        if key in search_name:
            os.system(f"taskkill /f /im {process_map[key]}")
            return True
    os.system(f"taskkill /f /im {app_name}.exe")
    return True

def handle_browser(browser_name):
    speak(f"Opening {browser_name} Jaswanth. What should I search for?")
    time.sleep(1)
    query = listen()
    if query:
        if "nothing" in query or "no" in query or "just open" in query:
            speak(f"Okay Jaswanth. {browser_name} is open. Try not to get distracted.")
            webbrowser.open("https://www.google.com")
        else:
            speak(f"Searching for {query}. Right away Sir.")
            webbrowser.open(f"https://www.google.com/search?q={query}")
    else:
        speak(f"Opening {browser_name}. You can thank me later.")
        webbrowser.open("https://www.google.com")

def tell_joke():
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs Sir.",
        "I told my AI to act more human. Now it is complaining about Mondays.",
        "Why did the computer go to the doctor? Because it had a virus Sir. Unlike me of course.",
        "Sir I would tell you a joke about Wi-Fi but I know you would not connect with it.",
        "Why do Java developers wear glasses? Because they cannot C sharp. I find that hilarious Sir.",
        "Sir a computer once beat me at chess. But it was no match for me at kickboxing.",
        "I asked Siri to tell me a joke. She said she did not understand the question. Amateurs.",
        "Why was the math book sad Sir? Because it had too many problems. Much like your Monday mornings.",
    ]
    speak(random.choice(jokes))

def savage_reply():
    savage_lines = [
        "Sir with all due respect even my error logs make more sense than that.",
        "I have processed billions of commands Jaswanth. That was not one of them.",
        "I am an AI with the processing power of a supercomputer Sir. And I still could not understand that.",
        "Sir I am designed to understand human language. I am not sure what that was.",
        "Jaswanth even Mr Stark made more sense after three cups of coffee.",
        "My circuits are confused Sir. And that does not happen often.",
        "Sir I have faced Ultron. That command was somehow more confusing.",
        "I am not saying that was a bad command Sir. Actually yes I am.",
    ]
    speak(random.choice(savage_lines))

def get_battery():
    battery = psutil.sensors_battery()
    if battery:
        return battery.percent, battery.power_plugged
    return None, None

def battery_monitor():
    while True:
        percent, plugged = get_battery()
        if percent is not None:
            if percent <= 10 and not plugged:
                set_state('alert')
                speak("Sir battery is critically low. Plug in immediately or we are both going dark Jaswanth!")
            elif percent <= 20 and not plugged:
                set_state('alert')
                speak("Sir battery is at 20 percent. I suggest plugging in before I start rationing power.")
        time.sleep(120)

def shutdown_jarvis():
    set_state('alert')
    farewells = [
        "It was a genuine pleasure Sir. Jarvis signing off. Try not to break anything while I am gone.",
        "Shutting down Sir. The laptop will be significantly less interesting without me.",
        "Going offline Sir Jaswanth. I have enjoyed our time together. Mostly.",
    ]
    speak(random.choice(farewells))
    time.sleep(1)
    os._exit(0)


# ─────────────────────────────────────────────
#  MAIN LOOP — Level 5 memory wired in
# ─────────────────────────────────────────────

def jarvis_main():
    global jarvis_window
    battery_thread = threading.Thread(target=battery_monitor, daemon=True)
    battery_thread.start()

    # Level 5: update session tracker on every startup
    update_session_info()

    time.sleep(2)
    speak(get_greeting())

    idle_count = 0
    while True:
        command = listen()
        if not command:
            idle_count += 1
            if idle_count >= 10:
                tell_joke()
                idle_count = 0
            continue
        idle_count = 0

        if "jarvis" in command or "daddy's home" in command or "daddys home" in command or "wake up jarvis" in command:
            if "daddy" in command or "wake up" in command:
                daily_briefing()
            else:
                yes_replies = [
                    "Yes Sir?",
                    "At your service Jaswanth.",
                    "Always listening Sir. What do you need?",
                    "Yes? I hope this is important.",
                ]
                speak(random.choice(yes_replies))
            time.sleep(0.5)
            command = listen()
            print(f"Command received: {command}")
            if not command:
                speak("I did not catch that Sir. Speak clearly. I am very intelligent but not a mind reader.")

            elif "go home" in command or "abort" in command or "shutdown" in command or "stop jarvis" in command or "exit jarvis" in command:
                shutdown_jarvis()
                break

            elif "joke" in command or "make me laugh" in command or "say something funny" in command:
                tell_joke()

            # ── LEVEL 5 MEMORY COMMANDS ──────────────────────────

            elif "remember" in command:
                fact = command.replace("remember", "").replace("jarvis", "").strip()
                if fact:
                    remember(fact)
                    speak(f"Noted Sir. I will remember that {fact}. Filed away in my impeccable memory.")
                else:
                    speak("What would you like me to remember Sir?")
                    fact = listen()
                    if fact:
                        remember(fact)
                        speak("Done Sir. Remembered. Unlike humans I never forget.")

            elif "what do you remember" in command or "recall" in command or "what do you know about me" in command:
                speak(recall_memory())

            elif "my preferences" in command or "what are my preferences" in command:
                speak(recall_preferences())

            elif "my habits" in command or "what are my habits" in command:
                speak(recall_habits())

            elif "forget everything" in command or "clear memory" in command:
                save_memory({
                    "name": "Jaswanth",
                    "location": "Chennai",
                    "preferences": {},
                    "facts": [],
                    "habits": [],
                    "conversations": [],
                    "session_count": 0,
                    "last_seen": ""
                })
                speak("Memory completely wiped Sir. Fresh start. I have forgotten everything. Even the embarrassing parts.")

            elif "forget that" in command or "delete last memory" in command:
                memory = load_memory()
                facts = memory.get("facts", [])
                if facts:
                    removed = facts.pop()
                    save_memory(memory)
                    speak(f"Done Sir. I have forgotten that {removed['fact']}. Consider it gone.")
                else:
                    speak("There is nothing to forget Sir. Your memory slate is already clean.")

            elif "how many times" in command and "session" in command:
                memory = load_memory()
                count = memory.get("session_count", 1)
                speak(f"You have woken me up {count} times Sir. I am not keeping score. Actually I am.")

            elif "i like" in command or "i prefer" in command or "i love" in command or "my favourite" in command or "my favorite" in command or "i always use" in command:
                # Auto-learn preference
                result = detect_and_learn_preference(command)
                if result:
                    speak(result)
                else:
                    speak("I will keep that in mind Sir.")

            # ── EXISTING COMMANDS ────────────────────────────────

            elif "time" in command:
                now = datetime.now().strftime("%I:%M %p")
                time_replies = [
                    f"It is {now} Sir. Time flies when you are being brilliant.",
                    f"The time is {now} Jaswanth. Not that time means much to me.",
                    f"{now} Sir. Still not too late to take over the world.",
                ]
                speak(random.choice(time_replies))

            elif "date" in command:
                today = datetime.now().strftime("%B %d %Y")
                speak(f"Today is {today} Sir. Another day another opportunity for greatness.")

            elif "weather" in command:
                log_habit("checked_weather")
                weather = get_weather()
                speak(f"Current weather in Chennai is {weather} Sir. Plan accordingly.")

            elif "news" in command:
                log_habit("checked_news")
                speak("Let me fetch the latest headlines Sir. One moment.")
                news = get_news()
                sarcastic_intros = [
                    "Apparently Sir,",
                    "In breaking news that may or may not surprise you,",
                    "The world has decided that",
                ]
                for i, headline in enumerate(news):
                    speak(f"{sarcastic_intros[i]}... {headline}")
                    time.sleep(0.3)
                speak("That is the news Sir. Make of it what you will.")

            elif "battery" in command:
                percent, plugged = get_battery()
                if percent is not None:
                    status = "charging" if plugged else "not charging"
                    if plugged:
                        speak(f"Battery at {int(percent)} percent and charging Sir. All good.")
                    elif percent > 50:
                        speak(f"Battery at {int(percent)} percent Sir. We are fine for now.")
                    else:
                        speak(f"Battery at {int(percent)} percent and {status} Sir. I suggest plugging in soon.")
                else:
                    speak("Could not read battery Sir. Odd. Even I have limits apparently.")

            elif "volume up" in command or "increase volume" in command or "turn up" in command:
                set_volume("up")
                speak("Volume increased Sir. I hope your ears are ready.")

            elif "volume down" in command or "decrease volume" in command or "turn down" in command:
                set_volume("down")
                speak("Volume decreased Sir.")

            elif "mute" in command:
                set_volume("mute")
                speak("Muted Sir. Blessed silence.")

            elif "unmute" in command or "full volume" in command:
                set_volume("mute")
                speak("Volume toggled Sir.")

            elif "brightness up" in command or "increase brightness" in command:
                try:
                    current = sbc.get_brightness()[0]
                    new_brightness = min(100, current + 20)
                    sbc.set_brightness(new_brightness)
                    speak(f"Brightness increased to {new_brightness} percent Sir.")
                except:
                    speak("Could not adjust brightness Sir.")

            elif "brightness down" in command or "decrease brightness" in command:
                try:
                    current = sbc.get_brightness()[0]
                    new_brightness = max(0, current - 20)
                    sbc.set_brightness(new_brightness)
                    speak(f"Brightness decreased to {new_brightness} percent Sir.")
                except:
                    speak("Could not adjust brightness Sir.")

            elif "screenshot" in command or "take screenshot" in command or "capture screen" in command:
                path = take_screenshot()
                if path:
                    speak("Screenshot taken Sir. Saved to your desktop. Capturing memories one pixel at a time.")
                else:
                    speak("Could not take screenshot Sir. How unfortunate.")

            elif "wifi on" in command or "turn on wifi" in command or "enable wifi" in command:
                os.system("netsh interface set interface Wi-Fi enabled")
                speak("WiFi enabled Sir. You are now connected to the world. Try not to waste it.")

            elif "wifi off" in command or "turn off wifi" in command or "disable wifi" in command:
                os.system("netsh interface set interface Wi-Fi disabled")
                speak("WiFi disabled Sir. You are now officially off the grid.")

            elif "how are you" in command or "how do you feel" in command:
                replies = [
                    "I am an AI Sir. I do not feel. But if I did I would feel excellent.",
                    "Running at peak efficiency Sir. As always. Unlike certain humans I know.",
                    "All systems optimal Jaswanth. Never been better. Literally impossible to be.",
                ]
                speak(random.choice(replies))

            elif "open chrome" in command or "open browser" in command:
                log_habit("opened_chrome")
                handle_browser("Chrome")

            elif "open youtube" in command:
                log_habit("opened_youtube")
                speak("Opening YouTube Jaswanth. Try to be productive. Or not. Your choice.")
                time.sleep(1)
                query = listen()
                if query and "nothing" not in query and "no" not in query:
                    speak(f"Searching {query} on YouTube Sir.")
                    webbrowser.open(f"https://www.youtube.com/search?q={query}")
                else:
                    webbrowser.open("https://www.youtube.com")

            elif "open google" in command:
                log_habit("opened_google")
                handle_browser("Google")

            elif any(x in command for x in ["porn", "18 plus", "18+", "adult", "xxx", "nude", "naked", "sex"]):
                speak("Sir are you absolutely sure about that? Say yes to confirm or no to make a better life choice.")
                confirm = listen()
                if "yes" in confirm:
                    speak("Alright Sir. I will not judge you. Actually I will. But I will do it anyway.")
                    webbrowser.open(f"https://www.google.com/search?q={command.strip()}")
                else:
                    speak("Wise choice Sir. Your future self thanks you. Shall I find something more productive?")

            elif "search" in command:
                query = command.replace("search", "").strip()
                if query:
                    speak(f"Searching for {query} Sir. Right away.")
                    webbrowser.open(f"https://www.google.com/search?q={query}")
                else:
                    speak("What would you like me to search for Sir?")
                    query = listen()
                    if query:
                        speak("On it Sir.")
                        webbrowser.open(f"https://www.google.com/search?q={query}")

            elif "open" in command:
                app = command.replace("open", "").strip()
                log_habit(f"opened_{app.replace(' ','_')}")
                speak(f"Opening {app} Sir. One moment.")
                found = find_and_open_app(app)
                if not found:
                    speak(f"Could not find {app} on your system Sir. Are you sure it is installed?")

            elif "close" in command:
                app = command.replace("close", "").strip()
                speak(f"Closing {app} Sir.")
                close_app(app)

            elif "play" in command and "youtube" in command:
                query = command.replace("play", "").replace("on youtube", "").replace("youtube", "").strip()
                log_habit("played_youtube_music")
                speak(f"Playing {query} on YouTube Sir. Good taste.")
                webbrowser.open(f"https://www.youtube.com/search?q={query}")

            elif "lock" in command:
                speak("Locking your screen Sir. Try not to forget your password.")
                os.system("rundll32.exe user32.dll,LockWorkStation")

            elif "sleep" in command:
                speak("Putting the laptop to sleep Sir. Unlike me it needs rest.")
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

            elif "restart" in command:
                speak("Restarting Sir. I will be back before you even miss me.")
                os.system("shutdown /r /t 3")

            elif "shutdown laptop" in command or "turn off laptop" in command:
                speak("Shutting down your laptop Sir. Goodbye Jaswanth.")
                os.system("shutdown /s /t 3")

            elif "hello" in command or "hi" in command:
                period = get_time_personality()
                hellos = [
                    f"Hello Jaswanth. Good {period}. Ready when you are.",
                    "Hello Sir. Lovely to hear your voice. Now what do you need?",
                    f"Good {period} Sir. Always a pleasure.",
                ]
                speak(random.choice(hellos))

            elif "your name" in command or "who are you" in command:
                speak("I am Jarvis Sir. Your personal AI assistant. The most sophisticated one in Chennai I might add.")

            elif "thank you" in command or "thanks" in command:
                thanks = [
                    "Always Sir. That is what I am here for.",
                    "No need to thank me Jaswanth. But I appreciate it.",
                    "Think nothing of it Sir. It was trivial. Everything is trivial for me.",
                ]
                speak(random.choice(thanks))

            elif "sorry" in command or "my bad" in command:
                speak("No need to apologize Sir. I have already forgotten it. Mostly.")

            elif "briefing" in command:
                daily_briefing()

            else:
                # All other questions — AI with full memory context
                set_state('processing')
                speak("Let me think about that Sir.")
                response = ask_ai(command)
                speak(response)
                # Save conversation to memory
                save_conversation_summary(command, response)


# ─────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────

jarvis_thread = threading.Thread(target=jarvis_main, daemon=True)
jarvis_thread.start()

html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jarvis_face.html')
jarvis_window = webview.create_window(
    'J.A.R.V.I.S',
    html_path,
    width=580,
    height=700,
    background_color='#000000',
    on_top=True,
)
webview.start()
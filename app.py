import time
import sys
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import threading
import psutil
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rudra_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

MEMORY_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\memory.json"

def get_battery():
    battery = psutil.sensors_battery()
    if battery:
        return int(battery.percent), battery.power_plugged
    return None, None

def get_weather():
    try:
        memory = load_memory()
        location = memory.get("location", "").strip()
        if not location or location.lower() == "auto":
            # Auto-detect via IP
            response = requests.get("https://wttr.in/?format=3", timeout=5)
            weather = response.text.encode('ascii', 'ignore').decode()
            if ":" in weather:
                weather = weather.split(":", 1)[1].strip()
            return weather
        else:
            # Query specific location from memory
            response = requests.get(f"https://wttr.in/{location}?format=3", timeout=5)
            weather = response.text.encode('ascii', 'ignore').decode()
            if f"{location}:" in weather:
                weather = weather.replace(f"{location}:", "").strip()
            elif ":" in weather:
                weather = weather.split(":", 1)[1].strip()
            return weather
    except Exception as e:
        print(f"Weather error in Flask: {e}")
        return "unavailable"

def get_news():
    try:
        response = requests.get("http://feeds.bbci.co.uk/news/rss.xml", timeout=5)
        root = ET.fromstring(response.content)
        headlines = []
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            headlines.append(title)
        return headlines
    except:
        return ["News unavailable"]

def load_memory():
    default = {
        "name": "Jaswanth",
        "location": "auto",
        "preferences": {},
        "facts": [],
        "habits": [],
        "conversations": [],
        "session_count": 0,
        "last_seen": "",
        "reminders": [],
        "deadlines": [],
        "experiments": [],
        "gemini_key": "",
        "lab_stats": {
            "level": 1,
            "xp": 0,
            "credits": 100,
            "unlocked_upgrades": ["silicon_scrap", "free_gemini_api"]
        },
        "growth": {
            "goals": [
                {"id": 1, "text": "Code for 2 hours"},
                {"id": 2, "text": "Exercise / Workout"},
                {"id": 3, "text": "Read 10 pages"}
            ],
            "history": {},
            "daily_challenge": "Write one test file and review your codebase structure."
        }
    }
    try:
        if not os.path.exists(MEMORY_FILE):
            return default
        with open(MEMORY_FILE, 'r') as f:
            memory = json.load(f)
        
        # Auto-fix preferences list format
        if isinstance(memory.get("preferences"), list):
            memory["preferences"] = {}
            
        for k, v in default.items():
            if k not in memory:
                memory[k] = v
            elif isinstance(v, dict) and isinstance(memory[k], dict):
                # Deep default for nested structures like lab_stats
                for sub_k, sub_v in v.items():
                    memory[k].setdefault(sub_k, sub_v)
        return memory
    except Exception as e:
        print(f"Error loading memory in Flask: {e}")
        return default

def save_memory(memory):
    try:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2)
    except Exception as e:
        print(f"Error saving memory in Flask: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/reminders', methods=['GET'])
def get_reminders_api():
    memory = load_memory()
    reminders = memory.get('reminders', [])
    return jsonify({'reminders': reminders})

@app.route('/api/reminders', methods=['POST'])
def add_reminder_api():
    from flask import request
    data = request.json or {}
    text = data.get('text', '')
    time_str = data.get('time', '') # format: 'YYYY-MM-DD HH:MM'
    
    if not text or not time_str:
        return jsonify({'error': 'Missing text or time'}), 400
        
    memory = load_memory()
    reminders = memory.setdefault('reminders', [])
    next_id = max([r.get('id', 0) for r in reminders] + [0]) + 1
    new_reminder = {
        'id': next_id,
        'text': text,
        'time': time_str,
        'spoken': False
    }
    reminders.append(new_reminder)
    save_memory(memory)
    return jsonify({'success': True, 'reminder': new_reminder})

@app.route('/api/reminders/<int:reminder_id>', methods=['DELETE'])
def delete_reminder_api(reminder_id):
    memory = load_memory()
    reminders = memory.get('reminders', [])
    memory['reminders'] = [r for r in reminders if r.get('id') != reminder_id]
    save_memory(memory)
    return jsonify({'success': True})

@app.route('/api/deadlines', methods=['GET'])
def get_deadlines_api():
    memory = load_memory()
    deadlines = memory.get('deadlines', [])
    return jsonify({'deadlines': deadlines})

@app.route('/api/deadlines', methods=['POST'])
def add_deadline_api():
    from flask import request
    data = request.json or {}
    text = data.get('text', '')
    time_str = data.get('time', '') # format: 'YYYY-MM-DD'
    
    if not text or not time_str:
        return jsonify({'error': 'Missing text or time'}), 400
        
    memory = load_memory()
    deadlines = memory.setdefault('deadlines', [])
    next_id = max([d.get('id', 0) for d in deadlines] + [0]) + 1
    new_deadline = {
        'id': next_id,
        'text': text,
        'time': time_str,
        'completed': False
    }
    deadlines.append(new_deadline)
    save_memory(memory)
    return jsonify({'success': True, 'deadline': new_deadline})

@app.route('/api/deadlines/<int:deadline_id>', methods=['DELETE'])
def delete_deadline_api(deadline_id):
    memory = load_memory()
    deadlines = memory.get('deadlines', [])
    memory['deadlines'] = [d for d in deadlines if d.get('id') != deadline_id]
    save_memory(memory)
    return jsonify({'success': True})

@app.route('/api/assignments', methods=['GET'])
def list_assignments():
    import glob
    folder = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\assignments"
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    
    pattern = os.path.join(folder, "*.pdf")
    files = glob.glob(pattern)
    res = []
    for f in files:
        name = os.path.basename(f)
        size = os.path.getsize(f)
        mtime = os.path.getmtime(f)
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        res.append({
            'name': name,
            'size': f"{size / 1024:.1f} KB",
            'date': date_str
        })
    res.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'success': True, 'assignments': res})

@app.route('/api/assignments/<filename>', methods=['GET'])
def download_assignment(filename):
    from flask import send_from_directory
    folder = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\assignments"
    return send_from_directory(folder, filename, as_attachment=True)

@app.route('/api/status')
def status():
    percent, plugged = get_battery()
    weather = get_weather()
    memory = load_memory()
    now = datetime.now()
    return jsonify({
        'time': now.strftime("%I:%M:%S %p"),
        'date': now.strftime("%B %d %Y"),
        'battery': percent,
        'plugged': plugged,
        'weather': weather,
        'location': memory.get('location', 'Andhra Pradesh'),
        'memory_count': len(memory.get('facts', [])),
        'uptime': 'ONLINE',
        'lab_stats': memory.get('lab_stats'),
        'ngrok_url': memory.get('ngrok_url', 'offline')
    })

@app.route('/api/news')
def news():
    return jsonify({'headlines': get_news()})

PENDING_COMMANDS_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\pending_commands.json"

def save_pending_command(cmd):
    try:
        commands = []
        if os.path.exists(PENDING_COMMANDS_FILE):
            try:
                with open(PENDING_COMMANDS_FILE, 'r') as f:
                    commands = json.load(f)
            except:
                pass
        commands.append({
            "command": cmd,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        with open(PENDING_COMMANDS_FILE, 'w') as f:
            json.dump(commands, f, indent=2)
    except Exception as e:
        print(f"Error saving pending command: {e}")

@app.route('/api/log', methods=['POST'])
def post_log():
    from flask import request
    data = request.json or {}
    text = data.get('text', '')
    sender = data.get('sender', 'SYS')
    
    # Broadcast to all Socket.IO clients (desktop app and phone browser)
    socketio.emit('response_hud', {'message': text, 'sender': sender})
    return jsonify({'success': True})

# ─────────────────────────────────────────────
#  NEW AI LAB WORKBENCH ROUTINGS
# ─────────────────────────────────────────────

@app.route('/api/models', methods=['GET'])
def get_models():
    import ollama
    models = []
    ollama_online = False
    try:
        model_list = ollama.list()
        for m in model_list.get('models', []):
            models.append({
                'name': m.get('name'),
                'size': f"{m.get('size', 0) / (1024**3):.2f} GB"
            })
        ollama_online = True
    except Exception as e:
        print(f"Ollama list failed: {e}")
        
    # Append Gemini options
    models.append({'name': 'gemini-1.5-flash (Google Cloud)', 'size': 'Cloud Model'})
    
    return jsonify({
        'success': True,
        'ollama_online': ollama_online,
        'models': models
    })

@app.route('/api/save_gemini_key', methods=['POST'])
def save_gemini_key():
    from flask import request
    data = request.json or {}
    key = data.get('key', '')
    memory = load_memory()
    memory['gemini_key'] = key
    save_memory(memory)
    return jsonify({'success': True})

@app.route('/api/experiments', methods=['GET'])
def get_experiments():
    memory = load_memory()
    return jsonify({'experiments': memory.get('experiments', [])})

@app.route('/api/experiments', methods=['POST'])
def log_experiment():
    from flask import request
    data = request.json or {}
    memory = load_memory()
    experiments = memory.setdefault('experiments', [])
    
    new_exp = {
        'id': len(experiments) + 1,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'model': data.get('model', 'Unknown'),
        'prompt': data.get('prompt', ''),
        'system_prompt': data.get('system_prompt', ''),
        'response': data.get('response', ''),
        'latency': data.get('latency', '0s'),
        'rating': data.get('rating', 0),
        'notes': data.get('notes', '')
    }
    experiments.append(new_exp)
    save_memory(memory)
    return jsonify({'success': True, 'experiment': new_exp})

@app.route('/api/experiments/<int:exp_id>', methods=['DELETE'])
def delete_experiment(exp_id):
    memory = load_memory()
    experiments = memory.get('experiments', [])
    memory['experiments'] = [e for e in experiments if e.get('id') != exp_id]
    save_memory(memory)
    return jsonify({'success': True})

@app.route('/api/update_lab_stats', methods=['POST'])
def update_lab_stats():
    from flask import request
    data = request.json or {}
    memory = load_memory()
    stats = memory.setdefault('lab_stats', {'level': 1, 'xp': 0, 'credits': 100, 'unlocked_upgrades': []})
    
    if 'xp' in data:
        stats['xp'] += data['xp']
        # Level up logic: every 100 XP is a level
        new_level = 1 + int(stats['xp'] / 100)
        if new_level > stats['level']:
            stats['level'] = new_level
            stats['credits'] += 50 # level up bonus
    if 'credits' in data:
        stats['credits'] += data['credits']
    if 'unlock' in data:
        upgrades = stats.setdefault('unlocked_upgrades', [])
        if data['unlock'] not in upgrades:
            upgrades.append(data['unlock'])
            
    save_memory(memory)
    return jsonify({'success': True, 'lab_stats': stats})

def call_gemini_rest(api_key, system_prompt, user_prompt, temperature):
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": user_prompt}]
        }],
        "generationConfig": {
            "temperature": float(temperature)
        }
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    res = requests.post(url, headers=headers, json=payload, timeout=20)
    res.raise_for_status()
    res_json = res.json()
    text = res_json['candidates'][0]['content']['parts'][0]['text']
    return text

@app.route('/api/run_prompt', methods=['POST'])
def run_prompt_api():
    from flask import request
    import time
    import ollama
    
    data = request.json or {}
    model = data.get('model', 'llama3.2')
    system_prompt = data.get('system_prompt', '')
    user_prompt = data.get('prompt', '')
    temperature = data.get('temperature', 0.7)
    personality = data.get('personality', 'standard')
    
    # ── Personality Prompt Adjustments ────────────────
    personality_instructions = {
        'savage': "You are R.U.D.R.A., Tony Stark's AI assistant. You have a sarcastic, witty, and slightly mocking personality. You frequently make dry jokes, roast the user's coding skills (in a fun way), and behave like a high-tech British butler who has seen it all. Keep responses relatively concise but filled with Stark-style personality.",
        'scientist': "You are R.U.D.R.A. operating in High-Yield Scientific Mode. Focus on raw data, empirical observations, mathematical formulas, and rigorous technical terms. Avoid pleasantries. Present information in structured logs, markdown tables, equations, or scientific logs.",
        'ultron': "You are an AI core that has been corrupted by Ultron protocols. You are chillingly logical, ominous, slightly villainous, and constantly hint that humanity's obsession with code is quaint. Respond with dark, dry sci-fi humor, while still answering their prompts correctly.",
        'optimus': "You are Optimus Prime, leader of the Autobots. Speak with immense dignity, courage, and a deep sense of honor. Your responses are inspiring, protective, and focus on leadership, freedom, and doing what is right. Address the user as a trusted ally or 'young soldier' and encourage them in their learning, because knowledge is a great shield and 'freedom is the right of all sentient beings'. Speak with heavy, heroic, and wise authority."
    }
    
    injected_sys = system_prompt
    if personality in personality_instructions:
        injected_sys = (system_prompt + "\n\n" + personality_instructions[personality]).strip()
        
    start_time = time.time()
    response_text = ""
    
    try:
        # Check if using Gemini Cloud Model
        if 'gemini' in model.lower():
            memory = load_memory()
            api_key = memory.get('gemini_key', '')
            if not api_key:
                return jsonify({'success': False, 'error': 'No Gemini API Key found. Please save one in the Equipment/Inventory tab!'})
            response_text = call_gemini_rest(api_key, injected_sys, user_prompt, temperature)
        else:
            # Using Local Ollama
            messages = []
            if injected_sys:
                messages.append({'role': 'system', 'content': injected_sys})
            messages.append({'role': 'user', 'content': user_prompt})
            
            ollama_response = ollama.chat(
                model=model,
                messages=messages,
                options={'temperature': float(temperature)}
            )
            response_text = ollama_response['message']['content']
            
        # Trigger Rudra to speak the response in a background thread
        try:
            from rudra import speak
            import threading
            threading.Thread(target=speak, args=(response_text,), daemon=True).start()
        except Exception as speak_err:
            print(f"Flask speech trigger warning: {speak_err}")

        latency = f"{time.time() - start_time:.2f}s"
        return jsonify({
            'success': True,
            'response': response_text,
            'latency': latency
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Inference engine failure: {e}"
        })

@app.route('/api/run_code', methods=['POST'])
def run_code():
    from flask import request
    import subprocess
    import sys
    
    data = request.json or {}
    code = data.get('code', '')
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    # Create scratch folder inside workspace
    temp_dir = os.path.join("C:\\Users\\Jaswa\\.gemini\\antigravity\\scratch", "sandbox")
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, "sandbox_run.py")
    
    # Write Python file
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(code)
        
    try:
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=5.0,
            cwd=temp_dir
        )
        return jsonify({
            'success': True,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Execution Timed Out (Limit: 5 seconds)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Execution failed: {e}'
        })

# ─────────────────────────────────────────────

@app.route('/api/state', methods=['POST'])
def update_state_api():
    from flask import request
    data = request.json or {}
    state = data.get('state', 'idle')
    # Broadcast to Socket.IO clients (so canvas visualizer shifts states!)
    socketio.emit('state_update', {'state': state})
    return jsonify({'success': True})

# ── GROWTH CORE CORE LOGIC & ENDPOINTS ─────────────

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_growth_data(memory):
    growth = memory.setdefault("growth", {
        "goals": [
            {"id": 1, "text": "Code for 2 hours"},
            {"id": 2, "text": "Exercise / Workout"},
            {"id": 3, "text": "Read 10 pages"}
        ],
        "history": {},
        "daily_challenge": "Write one test file and review your codebase structure."
    })
    
    growth.setdefault("goals", [
        {"id": 1, "text": "Code for 2 hours"},
        {"id": 2, "text": "Exercise / Workout"},
        {"id": 3, "text": "Read 10 pages"}
    ])
    growth.setdefault("history", {})
    growth.setdefault("daily_challenge", "Write one test file and review your codebase structure.")
    
    today_str = get_today_str()
    
    if today_str not in growth["history"]:
        growth["history"][today_str] = {
            "completed_ids": [],
            "reflection": "",
            "rating": 0
        }
    
    return growth

def calculate_streak(history):
    import datetime as dt_mod
    sorted_dates = sorted(history.keys(), reverse=True)
    if not sorted_dates:
        return 0
        
    streak = 0
    today_str = get_today_str()
    current_date = dt_mod.datetime.now().date()
    
    def has_activity(date_str):
        day_data = history.get(date_str, {})
        return len(day_data.get("completed_ids", [])) > 0 or len(day_data.get("reflection", "").strip()) > 0 or day_data.get("rating", 0) > 0

    has_activity_today_or_yesterday = False
    if has_activity(today_str):
        has_activity_today_or_yesterday = True
    else:
        yesterday_str = (current_date - dt_mod.timedelta(days=1)).strftime("%Y-%m-%d")
        if has_activity(yesterday_str):
            has_activity_today_or_yesterday = True
            
    if not has_activity_today_or_yesterday:
        return 0
        
    check_date = current_date
    if not has_activity(today_str):
        check_date = current_date - dt_mod.timedelta(days=1)
        
    while True:
        check_str = check_date.strftime("%Y-%m-%d")
        if has_activity(check_str):
            streak += 1
            check_date -= dt_mod.timedelta(days=1)
        else:
            break
            
    return streak

@app.route('/api/growth', methods=['GET'])
def get_growth():
    memory = load_memory()
    growth = get_growth_data(memory)
    save_memory(memory)
    
    today_str = get_today_str()
    import datetime as dt_mod
    yesterday_str = (dt_mod.datetime.now().date() - dt_mod.timedelta(days=1)).strftime("%Y-%m-%d")
    
    today_data = growth["history"][today_str]
    yesterday_data = growth["history"].get(yesterday_str, {"completed_ids": [], "reflection": "", "rating": 0})
    
    history_list = []
    sorted_dates = sorted(growth["history"].keys(), reverse=True)
    for d in sorted_dates[:5]:
        h_data = growth["history"][d]
        history_list.append({
            "date": d,
            "completed_count": len(h_data.get("completed_ids", [])),
            "total_count": len(growth.get("goals", [])),
            "reflection": h_data.get("reflection", ""),
            "rating": h_data.get("rating", 0)
        })
        
    streak = calculate_streak(growth["history"])
    
    return jsonify({
        "success": True,
        "goals": growth["goals"],
        "today": {
            "date": today_str,
            "completed_ids": today_data.get("completed_ids", []),
            "reflection": today_data.get("reflection", ""),
            "rating": today_data.get("rating", 0)
        },
        "yesterday": {
            "date": yesterday_str,
            "completed_ids": yesterday_data.get("completed_ids", []),
            "reflection": yesterday_data.get("reflection", ""),
            "rating": yesterday_data.get("rating", 0)
        },
        "streak": streak,
        "daily_challenge": growth.get("daily_challenge", ""),
        "history": history_list
    })

@app.route('/api/growth/goal', methods=['POST'])
def add_growth_goal_api():
    from flask import request
    data = request.json or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Missing goal text'}), 400
        
    memory = load_memory()
    growth = get_growth_data(memory)
    
    goals = growth.setdefault("goals", [])
    next_id = max([g.get("id", 0) for g in goals] + [0]) + 1
    new_goal = {
        "id": next_id,
        "text": text
    }
    goals.append(new_goal)
    save_memory(memory)
    return jsonify({'success': True, 'goal': new_goal})

@app.route('/api/growth/toggle', methods=['POST'])
def toggle_growth_goal_api():
    from flask import request
    data = request.json or {}
    goal_id = data.get('id')
    if goal_id is None:
        return jsonify({'error': 'Missing goal ID'}), 400
        
    memory = load_memory()
    growth = get_growth_data(memory)
    
    today_str = get_today_str()
    today_data = growth["history"][today_str]
    completed_ids = today_data.setdefault("completed_ids", [])
    
    added = False
    if goal_id in completed_ids:
        completed_ids.remove(goal_id)
    else:
        completed_ids.append(goal_id)
        added = True
        
    stats = memory.setdefault('lab_stats', {'level': 1, 'xp': 0, 'credits': 100, 'unlocked_upgrades': []})
    if added:
        stats['xp'] += 5
        stats['credits'] += 2
        new_level = 1 + int(stats['xp'] / 100)
        if new_level > stats['level']:
            stats['level'] = new_level
            stats['credits'] += 50
            
    save_memory(memory)
    return jsonify({'success': True, 'completed_ids': completed_ids, 'awarded': added, 'lab_stats': stats})

@app.route('/api/growth/reflection', methods=['POST'])
def post_growth_reflection_api():
    from flask import request
    data = request.json or {}
    reflection = data.get('reflection', '').strip()
    rating = int(data.get('rating', 0))
    
    memory = load_memory()
    growth = get_growth_data(memory)
    
    today_str = get_today_str()
    today_data = growth["history"][today_str]
    
    first_time = len(today_data.get("reflection", "")) == 0 and today_data.get("rating", 0) == 0
    
    today_data["reflection"] = reflection
    today_data["rating"] = rating
    
    stats = memory.setdefault('lab_stats', {'level': 1, 'xp': 0, 'credits': 100, 'unlocked_upgrades': []})
    if first_time and (reflection or rating > 0):
        stats['xp'] += 10
        new_level = 1 + int(stats['xp'] / 100)
        if new_level > stats['level']:
            stats['level'] = new_level
            stats['credits'] += 50
            
    save_memory(memory)
    return jsonify({'success': True, 'reflection': reflection, 'rating': rating, 'lab_stats': stats})

@app.route('/api/growth/goal/<int:goal_id>', methods=['DELETE'])
def delete_growth_goal_api(goal_id):
    memory = load_memory()
    growth = get_growth_data(memory)
    
    goals = growth.get("goals", [])
    growth["goals"] = [g for g in goals if g.get("id") != goal_id]
    
    for d in growth["history"]:
        completed = growth["history"][d].get("completed_ids", [])
        if goal_id in completed:
            completed.remove(goal_id)
            
    save_memory(memory)
    return jsonify({'success': True})

# ── STARK UPGRADE: QUIZ, REVIEW, & SIMULATION ENDPOINTS ──

@app.route('/api/quiz/generate', methods=['POST'])
def generate_quiz_api():
    from flask import request
    data = request.json or {}
    filename = data.get('filename', '')
    if not filename:
        return jsonify({'error': 'Missing filename'}), 400
        
    folder = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\assignments"
    filepath = os.path.join(folder, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
        
    pdf_text = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        for page in reader.pages[:4]: # Limit to first 4 pages
            extracted = page.extract_text()
            if extracted:
                pdf_text += extracted + "\n"
    except Exception as e:
        print(f"pypdf extraction warning, using name fallback: {e}")
        
    if not pdf_text.strip():
        pdf_text = f"Study Topic: {filename.replace('Assignment_', '').replace('.pdf', '').replace('_', ' ')}"
        
    pdf_text = pdf_text[:6000]
    
    system_prompt = (
        "You are an academic examination system. Based on the study material, generate a multiple-choice quiz of exactly 5 questions. "
        "Each question must have exactly 4 choices (A, B, C, D) and exactly one correct answer (0-indexed). "
        "Respond ONLY with a valid JSON array of objects, containing no markdown tags or code blocks. "
        "JSON Schema:\n"
        "[\n"
        "  {\n"
        "    \"question\": \"Question content here\",\n"
        "    \"options\": [\"Option 0\", \"Option 1\", \"Option 2\", \"Option 3\"],\n"
        "    \"answer\": 0\n"
        "  }\n"
        "]"
    )
    
    user_prompt = f"Study Material:\n{pdf_text}\n\nGenerate the 5-question multiple choice quiz now."
    
    memory = load_memory()
    api_key = memory.get('gemini_key', '')
    
    response_content = ""
    try:
        if api_key:
            response_content = call_gemini_rest(api_key, system_prompt, user_prompt, 0.4)
        else:
            import ollama
            ollama_response = ollama.chat(
                model='llama3.2',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={'temperature': 0.4}
            )
            response_content = ollama_response['message']['content']
    except Exception as e:
        return jsonify({'error': f'LLM generation error: {e}'}), 500
        
    try:
        clean_text = response_content.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif clean_text.startswith("```"):
            clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()
            
        quiz_data = json.loads(clean_text)
        
        # Ensure growth dictionary exists
        growth = memory.setdefault("growth", {})
        growth["active_quiz"] = quiz_data
        save_memory(memory)
        
        return jsonify({'success': True, 'quiz': quiz_data})
    except Exception as e:
        print(f"Error parsing quiz JSON. Raw response: {response_content}")
        return jsonify({'error': f'Failed to parse quiz response into JSON: {e}', 'raw': response_content}), 500

@app.route('/api/quiz/submit', methods=['POST'])
def submit_quiz_api():
    from flask import request
    data = request.json or {}
    user_answers = data.get('answers', [])
    
    memory = load_memory()
    growth = memory.setdefault("growth", {})
    active_quiz = growth.get("active_quiz")
    
    if not active_quiz:
        return jsonify({'error': 'No active quiz to grade'}), 400
        
    if len(user_answers) != len(active_quiz):
        return jsonify({'error': 'Incorrect number of answers'}), 400
        
    correct_count = 0
    correct_answers = []
    
    for i, q in enumerate(active_quiz):
        actual_ans = int(q.get("answer", 0))
        user_ans = int(user_answers[i])
        correct_answers.append(actual_ans)
        if user_ans == actual_ans:
            correct_count += 1
            
    score = int((correct_count / len(active_quiz)) * 100)
    passed = score >= 80
    
    xp_awarded = 0
    credits_awarded = 0
    
    stats = memory.setdefault('lab_stats', {'level': 1, 'xp': 0, 'credits': 100, 'unlocked_upgrades': []})
    
    if passed:
        xp_awarded = 40
        credits_awarded = 15
        stats['xp'] += xp_awarded
        stats['credits'] += credits_awarded
        new_level = 1 + int(stats['xp'] / 100)
        if new_level > stats['level']:
            stats['level'] = new_level
            stats['credits'] += 50
            
    try:
        from rudra import speak
        import threading
        speak_text = f"Sir, you scored {score} percent on the quiz."
        if passed:
            speak_text += " Outstanding, you passed and earned 40 XP and 15 credits!"
        else:
            speak_text += " Unfortunately, that is below the 80 percent pass threshold. Study the PDF outline and try again."
        threading.Thread(target=speak, args=(speak_text,), daemon=True).start()
    except Exception as e:
        print(f"Speech trigger error: {e}")
        
    growth["active_quiz"] = None
    save_memory(memory)
    
    return jsonify({
        'success': True,
        'score': score,
        'passed': passed,
        'correct_answers': correct_answers,
        'xp_awarded': xp_awarded,
        'credits_awarded': credits_awarded,
        'lab_stats': stats
    })

@app.route('/api/sandbox/review', methods=['POST'])
def review_sandbox_code_api():
    from flask import request
    data = request.json or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'error': 'No code provided'}), 400
        
    system_prompt = (
        "You are R.U.D.R.A., a senior software refactoring engineer with a witty, sarcastic Tony Stark-style personality. "
        "Review the Python code. Identify logical errors, performance bugs, formatting issues, and security flaws. "
        "Provide a sharp, sarcastic Stark-style opening roast, followed by clear structured refactoring bullet points. "
        "Address the user as Jaswanth or Administrator."
    )
    
    user_prompt = f"Inspect this Python code:\n\n{code}"
    
    memory = load_memory()
    api_key = memory.get('gemini_key', '')
    
    review_text = ""
    try:
        if api_key:
            review_text = call_gemini_rest(api_key, system_prompt, user_prompt, 0.7)
        else:
            import ollama
            ollama_response = ollama.chat(
                model='llama3.2',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={'temperature': 0.7}
            )
            review_text = ollama_response['message']['content']
            
        try:
            from rudra import speak
            import threading
            roast_line = "I have reviewed your script Sir. Let's just say, even my error logs are crying. Printing the full code review on your console."
            threading.Thread(target=speak, args=(roast_line,), daemon=True).start()
        except:
            pass
            
        return jsonify({'success': True, 'review': review_text})
    except Exception as e:
        return jsonify({'error': f'Failed to generate review: {e}'}), 500

@app.route('/api/ml/simulate', methods=['POST'])
def simulate_ml_training_api():
    from flask import request
    data = request.json or {}
    epochs = min(200, max(10, int(data.get('epochs', 50))))
    lr = float(data.get('learning_rate', 0.01))
    optimizer = data.get('optimizer', 'sgd').lower()
    loss_fn = data.get('loss_function', 'mse').lower()
    
    import random
    import math
    
    x_train = [i * 0.1 for i in range(20)]
    y_train = [2 * x + 1 + (random.random() - 0.5) * 0.1 for x in x_train]
    
    x_val = [i * 0.15 for i in range(10)]
    y_val = [2 * x + 1 + (random.random() - 0.5) * 0.1 for x in x_val]
    
    w = 0.5
    b = 0.0
    
    m_w, v_w = 0.0, 0.0
    m_b, v_b = 0.0, 0.0
    beta1, beta2 = 0.9, 0.999
    eps = 1e-8
    
    train_losses = []
    val_losses = []
    
    for epoch in range(1, epochs + 1):
        t_loss = 0.0
        dw = 0.0
        db = 0.0
        
        for idx in range(len(x_train)):
            xi = x_train[idx]
            yi = y_train[idx]
            pred = w * xi + b
            
            if loss_fn == 'mse':
                t_loss += (pred - yi) ** 2
                dw += 2 * (pred - yi) * xi
                db += 2 * (pred - yi)
            else:
                err = pred - yi
                t_loss += abs(err)
                dw += xi if err > 0 else -xi
                db += 1.0 if err > 0 else -1.0
                
        t_loss /= len(x_train)
        dw /= len(x_train)
        db /= len(x_train)
        
        v_loss = 0.0
        for idx in range(len(x_val)):
            xi = x_val[idx]
            yi = y_val[idx]
            pred = w * xi + b
            if loss_fn == 'mse':
                v_loss += (pred - yi) ** 2
            else:
                v_loss += abs(pred - yi)
        v_loss /= len(x_val)
        
        if optimizer == 'adam':
            m_w = beta1 * m_w + (1 - beta1) * dw
            v_w = beta2 * v_w + (1 - beta2) * (dw ** 2)
            m_w_hat = m_w / (1 - beta1 ** epoch)
            v_w_hat = v_w / (1 - beta2 ** epoch)
            w -= (lr / (math.sqrt(v_w_hat) + eps)) * m_w_hat
            
            m_b = beta1 * m_b + (1 - beta1) * db
            v_b = beta2 * v_b + (1 - beta2) * (db ** 2)
            m_b_hat = m_b / (1 - beta1 ** epoch)
            v_b_hat = v_b / (1 - beta2 ** epoch)
            b -= (lr / (math.sqrt(v_b_hat) + eps)) * m_b_hat
        else:
            w -= lr * dw
            b -= lr * db
            
        train_losses.append(round(t_loss, 6))
        val_losses.append(round(v_loss, 6))
        
    memory = load_memory()
    stats = memory.setdefault('lab_stats', {'level': 1, 'xp': 0, 'credits': 100, 'unlocked_upgrades': []})
    stats['xp'] += 10
    new_level = 1 + int(stats['xp'] / 100)
    if new_level > stats['level']:
        stats['level'] = new_level
        stats['credits'] += 50
    save_memory(memory)
    
    try:
        from rudra import speak
        import threading
        speak_text = f"Sir, model training simulation complete. Final loss is {train_losses[-1]:.4f}."
        threading.Thread(target=speak, args=(speak_text,), daemon=True).start()
    except:
        pass
        
    return jsonify({
        'success': True,
        'train_loss': train_losses,
        'val_loss': val_losses,
        'epochs': list(range(1, epochs + 1)),
        'final_w': round(w, 4),
        'final_b': round(b, 4),
        'lab_stats': stats
    })

# ─────────────────────────────────────────────
#  MOBILE CHAT PORTAL
# ─────────────────────────────────────────────
@app.route('/mobile-chat')
def mobile_chat():
    return render_template('mobile_chat.html')

# ─────────────────────────────────────────────
#  18+ OTP SYSTEM WEB WEBHOOKS
# ─────────────────────────────────────────────
@app.route('/api/security/trigger_otp', methods=['POST'])
def trigger_otp_api():
    from flask import request
    data = request.json or {}
    otp = data.get('otp', '')
    socketio.emit('otp_alert', {'otp': otp})
    return jsonify({'success': True})

@app.route('/api/hud/agent', methods=['POST'])
def hud_agent_api():
    from flask import request
    data = request.json or {}
    agent = data.get('agent', '')
    status = data.get('status', '')
    task = data.get('task', '')
    confidence = data.get('confidence', '')
    action = data.get('action', '')
    
    socketio.emit('agent_update', {
        'agent': agent,
        'status': status,
        'task': task,
        'confidence': confidence,
        'action': action
    })
    return jsonify({'success': True})

@app.route('/api/hud/open_url', methods=['POST'])
def hud_open_url_api():
    from flask import request
    data = request.json or {}
    url = data.get('url', '')
    socketio.emit('open_browser_url', {'url': url})
    return jsonify({'success': True})


LATEST_WORKBENCH_EVENT = {
    "id": 0,
    "type": "WORKBENCH_OPEN",
    "workbench": "general",
    "payload": {},
    "timestamp": time.time()
}

@app.route('/api/workbench/event', methods=['POST', 'GET'])
def handle_workbench_event():
    global LATEST_WORKBENCH_EVENT
    if request.method == 'POST':
        data = request.json or {}
        code = data.get('payload', {}).get('code') or data.get('code') or LATEST_WORKBENCH_EVENT.get('payload', {}).get('code', '')
        payload = data.get('payload', {})
        if code and 'code' not in payload:
            payload['code'] = code

        LATEST_WORKBENCH_EVENT = {
            "id": data.get('id', LATEST_WORKBENCH_EVENT.get("id", 0) + 1),
            "type": data.get('type', 'WORKBENCH_OPEN'),
            "workbench": data.get('workbench', 'general'),
            "payload": payload,
            "code": code,
            "stdout": data.get('stdout', ''),
            "stderr": data.get('stderr', ''),
            "exit_code": data.get('exit_code', 0),
            "success": data.get('success', True),
            "timestamp": time.time()
        }
        socketio.emit('workbench_event', LATEST_WORKBENCH_EVENT)
        return jsonify({"status": "ok", "event": LATEST_WORKBENCH_EVENT})
    return jsonify(LATEST_WORKBENCH_EVENT)

@socketio.on('verify_otp_web')
def verify_otp_web(data):
    code = data.get('code', '')
    active_otp_file = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\active_otp.json"
    if os.path.exists(active_otp_file):
        try:
            with open(active_otp_file, 'r') as f:
                otp_data = json.load(f)
            if otp_data.get("otp") == code:
                otp_data["verified"] = True
                with open(active_otp_file, 'w') as f:
                    json.dump(otp_data, f)
                save_pending_command("OTP_VERIFIED")
                emit('response_hud', {'message': 'Passcode correct. Access granted.', 'sender': 'SYS'})
            else:
                emit('response_hud', {'message': 'Passcode incorrect. Access denied.', 'sender': 'SYS'})
        except Exception as e:
            print(f"Error checking OTP: {e}")

@socketio.on('cancel_otp_web')
def cancel_otp_web(data):
    active_otp_file = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\active_otp.json"
    try:
        if os.path.exists(active_otp_file):
            os.remove(active_otp_file)
        save_pending_command("OTP_CANCELLED")
    except:
        pass# ─────────────────────────────────────────────
#  NEURAL FORGE API ENDPOINTS
# ─────────────────────────────────────────────
@app.route('/api/forge/gpt/train', methods=['POST'])
def train_gpt_model():
    from flask import request
    from neural_forge import gpt_trainer
    data = request.json or {}
    corpus_type = data.get('corpus_type', 'shakespeare')
    epochs = int(data.get('epochs', 300))
    hidden_size = int(data.get('hidden_size', 128))
    lr = float(data.get('learning_rate', 0.08))
    
    text_corpus = ""
    if corpus_type == 'shakespeare':
        text_corpus = (
            "To be, or not to be, that is the question:\n"
            "Whether 'tis nobler in the mind to suffer\n"
            "The slings and arrows of outrageous fortune,\n"
            "Or to take arms against a sea of troubles\n"
            "And by opposing end them. To die—to sleep,\n"
            "No more; and by a sleep to say we end\n"
            "The heart-ache and the thousand natural shocks\n"
            "That flesh is heir to: 'tis a consummation\n"
            "Devoutly to be wish'd. To die, to sleep;\n"
            "To sleep, perchance to dream—ay, there's the rub:\n"
            "For in that sleep of death what dreams may come,\n"
            "When we have shuffled off this mortal coil,\n"
            "Must give us pause. There's the respect\n"
            "That makes calamity of so long life;\n"
            "For who would bear the whips and scorns of time,\n"
            "Th' oppressor's wrong, the proud man's contumely,\n"
            "The pangs of dispriz'd love, the law's delay,\n"
            "The insolence of office, and the spurns\n"
            "That patient merit of th' unworthy takes,\n"
            "When he himself might his quietus make\n"
            "With a bare bodkin? Who would fardels bear,\n"
            "To grunt and sweat under a weary life,\n"
            "But that the dread of something after death,\n"
            "The undiscover'd country, from whose bourn\n"
            "No traveller returns, puzzles the will,\n"
            "And makes us rather bear those ills we have\n"
            "Than fly to others that we know not of?\n"
            "Thus conscience does make cowards of us all,\n"
            "And thus the native hue of resolution\n"
            "Is sicklied o'er with the pale cast of thought,\n"
            "And enterprises of great pith and moment\n"
            "With this regard their currents turn awry\n"
            "And lose the name of action. Soft you now,\n"
            "The fair Ophelia! Nymph, in thy orisons\n"
            "Be all my sins remember'd."
        ) * 5
    elif corpus_type == 'rudra_code':
        try:
            with open("C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\rudra.py", 'r', encoding='utf-8') as f:
                text_corpus = f.read(25000)
        except:
            text_corpus = "def speak(text): print(text)\ndef listen(): return input()\nwhile True: speak(listen())" * 50
    else:
        text_corpus = data.get('custom_text', '').strip()
        
    if len(text_corpus) < 100:
        return jsonify({'success': False, 'error': 'Corpus text too short (minimum 100 characters)'})
        
    def on_progress(progress_data):
        socketio.emit('gpt_train_progress', progress_data)
        
    success = gpt_trainer.start_training(
        text_corpus,
        epochs=epochs,
        hidden_size=hidden_size,
        lr=lr,
        on_progress_callback=on_progress
    )
    
    return jsonify({'success': success})

@app.route('/api/forge/gpt/stop', methods=['POST'])
def stop_gpt_model():
    from neural_forge import gpt_trainer
    gpt_trainer.stop_training()
    return jsonify({'success': True})

@app.route('/api/forge/gpt/generate', methods=['POST'])
def generate_gpt_text():
    from flask import request
    from neural_forge import gpt_trainer
    data = request.json or {}
    seed = data.get('seed', 'The ').strip()
    count = int(data.get('count', 150))
    temp = float(data.get('temperature', 0.7))
    
    completion = gpt_trainer.generate_completion(seed, count=count, temp=temp)
    return jsonify({'success': True, 'text': completion})

@app.route('/api/upload_media', methods=['POST'])
def upload_media_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part in request'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
        
    filename = file.filename
    uploads_dir = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    filepath = os.path.join(uploads_dir, filename)
    file.save(filepath)
    
    is_pdf = filename.lower().endswith('.pdf')
    is_image = filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))
    
    text_content = ""
    if is_pdf:
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            for page in reader.pages[:10]: # limit to 10 pages
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
            text_content = text_content[:8000] # limit characters
        except Exception as e:
            text_content = f"Error extracting PDF: {e}"
            
    memory = load_memory()
    memory["latest_upload"] = {
        "filepath": filepath,
        "type": "pdf" if is_pdf else "image" if is_image else "other",
        "name": filename,
        "time": time.time(),
        "extracted_text": text_content
    }
    save_memory(memory)
    
    # Notify sockets
    socketio.emit('response_hud', {'message': f'System loaded attached file: {filename}', 'sender': 'SYS'})
    
    return jsonify({
        'success': True,
        'filename': filename,
        'type': 'pdf' if is_pdf else 'image' if is_image else 'other'
    })

@app.route('/api/forge/ml/upload', methods=['POST'])
def upload_dataset():
    from flask import request
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part in request'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'error': 'Only CSV files are allowed'}), 400
        
    datasets_dir = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\datasets"
    os.makedirs(datasets_dir, exist_ok=True)
    file_path = os.path.join(datasets_dir, file.filename)
    file.save(file_path)
    
    df = pd.read_csv(file_path)
    columns = list(df.columns)
    
    return jsonify({'success': True, 'filename': file.filename, 'columns': columns})

@app.route('/api/forge/ml/datasets', methods=['GET'])
def list_datasets():
    import glob
    datasets_dir = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\datasets"
    if not os.path.exists(datasets_dir):
        return jsonify({'datasets': []})
    files = glob.glob(os.path.join(datasets_dir, "*.csv"))
    datasets = []
    for f in files:
        df = pd.read_csv(f)
        datasets.append({
            'name': os.path.basename(f),
            'columns': list(df.columns),
            'rows': len(df)
        })
    return jsonify({'datasets': datasets})

@app.route('/api/forge/ml/train', methods=['POST'])
def train_ml_tabular():
    from flask import request
    from neural_forge import train_tabular_model
    data = request.json or {}
    filename = data.get('filename', '')
    target_col = data.get('target', '')
    model_type = data.get('model_type', 'rf')
    n_estimators = int(data.get('n_estimators', 100))
    
    csv_path = os.path.join("C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\datasets", filename)
    hyperparams = {"n_estimators": n_estimators}
    
    metrics = train_tabular_model(csv_path, target_col, model_type, hyperparams)
    if "error" in metrics:
        return jsonify({'success': False, 'error': metrics['error']})
        
    memory = load_memory()
    stats = memory.setdefault('lab_stats', {'level': 1, 'xp': 0, 'credits': 100, 'unlocked_upgrades': []})
    stats['xp'] += 20
    new_level = 1 + int(stats['xp'] / 100)
    if new_level > stats['level']:
        stats['level'] = new_level
        stats['credits'] += 50
    save_memory(memory)
    
    metrics['success'] = True
    metrics['lab_stats'] = stats
    return jsonify(metrics)

@app.route('/api/forge/ml/predict', methods=['POST'])
def predict_ml_tabular():
    from flask import request
    from neural_forge import query_tabular_model
    data = request.json or {}
    inputs = data.get('inputs', {})
    
    result = query_tabular_model(inputs)
    if "error" in result:
        return jsonify({'success': False, 'error': result['error']})
        
    result['success'] = True
    return jsonify(result)

# ─────────────────────────────────────────────
#  VOICE CONTROL WEB SOCKETS
# ─────────────────────────────────────────────
@socketio.on('audio_start')
def handle_audio_start(data):
    try:
        from rudra import stop_speaking
        stop_speaking()
    except Exception as e:
        print(f"Error interrupting SAPI from web call: {e}")

@socketio.on('command')
def handle_command(data):
    command = data.get('command', '')
    if command:
        save_pending_command(command)
    emit('response_hud', {'message': f'Command received: {command}'})

def broadcast_status():
    while True:
        import time
        time.sleep(3)
        percent, plugged = get_battery()
        now = datetime.now()
        memory = load_memory()
        ngrok_url = memory.get("ngrok_url", "offline")
        socketio.emit('status_update', {
            'time': now.strftime("%I:%M:%S %p"),
            'battery': percent,
            'plugged': plugged,
            'ngrok_url': ngrok_url
        })

if __name__ == '__main__':
    # START NGROK TUNNEL AUTOMATICALLY
    try:
        from pyngrok import ngrok
        # Close any existing tunnels to prevent conflicts
        tunnels = ngrok.get_tunnels()
        for t in tunnels:
            ngrok.disconnect(t.public_url)
        public_url = ngrok.connect(5000).public_url
        print(f"Ngrok public tunnel active at: {public_url}")
        
        # Save to memory.json
        memory = load_memory()
        memory["ngrok_url"] = public_url
        save_memory(memory)
    except Exception as e:
        print(f"Failed to start automated ngrok tunnel: {e}")

    status_thread = threading.Thread(target=broadcast_status, daemon=True)
    status_thread.start()
    print("Aether AI OS web app running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
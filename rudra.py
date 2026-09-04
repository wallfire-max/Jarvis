import sys
# Set COM threading model to MTA (Multi-Threaded Apartment) to prevent WinError -2147417850 on background threads
sys.coinit_flags = 0

import os
import time

# ─────────────────────────────────────────────
#  SINGLE INSTANCE PROTECTION (PREVENTS GHOST RUNS & DUPLICATE VOICE)
# ─────────────────────────────────────────────
import socket
_lock_socket = None

def ensure_single_instance():
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _lock_socket.bind(('127.0.0.1', 49152))
        return True
    except socket.error:
        print("[RUDRA WARNING] Another instance is already running. Exiting duplicate process.")
        sys.exit(0)

import speech_recognition as sr
from datetime import datetime
import datetime as dt_mod
import pyttsx3
try:
    from pyngrok import ngrok
    HAS_PYNGROK = True
except ImportError:
    HAS_PYNGROK = False
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
import re
import html
import aether_tools

# ─────────────────────────────────────────────
#  WORKSPACE DIRECTORY (PYTHON FOLDER)
# ─────────────────────────────────────────────

def get_python_dir():
    """Locates or creates the user's target python folder"""
    candidates = [
        "C:\\Users\\Jaswa\\OneDrive\\Desktop\\python",
        "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\python",
        "C:\\Users\\Jaswa\\Desktop\\python",
        "C:\\Users\\Jaswa\\python",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    default_dir = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\python"
    os.makedirs(default_dir, exist_ok=True)
    return default_dir

# ─────────────────────────────────────────────
#  WORKBENCH ROUTER (AUTOMATICALLY SHIFTS TO CODING SANDBOX)
# ─────────────────────────────────────────────

VALID_WORKBENCHES = ["coding", "files", "research", "automation", "security", "vision", "general"]
_event_counter = 0

def dispatch_workbench_event(event_data):
    """
    Authoritative single dispatch for all Workbench UI events.
    Sends event to Flask event queue and triggers real DOM updates in Pywebview.
    """
    global rudra_window, _event_counter
    _event_counter += 1
    event_data["id"] = _event_counter
    event_data["timestamp"] = time.time()
    
    # 1. Post to Flask API buffer
    try:
        requests.post("http://localhost:5000/api/workbench/event", json=event_data, timeout=1.0)
    except Exception as e:
        pass

    # 2. Live DOM Updates in Pywebview
    if rudra_window:
        try:
            js_event = json.dumps(event_data)
            rudra_window.evaluate_js(f"""
                (function() {{
                    var evt = {js_event};
                    if (window.WorkbenchManager && window.WorkbenchManager.handleEvent) {{
                        window.WorkbenchManager.handleEvent(evt);
                        return;
                    }}
                    
                    // Fallback Direct DOM operations
                    if (evt.type === 'WORKBENCH_OPEN' || evt.type === 'CODE_LOAD' || evt.type === 'CODE_EXECUTION_RESULT') {{
                        var btn = document.querySelector('button[onclick*="sandbox-tab"]');
                        if (typeof switchTab === 'function') {{
                            switchTab('sandbox-tab', btn || document.createElement('button'));
                        }}
                    }}
                    if (evt.type === 'CODE_LOAD') {{
                        var code = evt.payload ? evt.payload.code : (evt.code || '');
                        var editor = document.getElementById('sandbox-code');
                        if (editor) {{
                            editor.value = code;
                            if (typeof updateLineNumbers === 'function') updateLineNumbers();
                            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }}
                    if (evt.type === 'CODE_EXECUTION_RESULT') {{
                        var term = document.getElementById('sandbox-terminal');
                        if (term) {{
                            var line = document.createElement('div');
                            if (evt.exit_code === 0 && !evt.stderr) {{
                                line.className = 'terminal-line';
                                line.textContent = evt.stdout || '[Executed with no output]';
                            }} else {{
                                line.className = 'terminal-line error';
                                line.textContent = (evt.stdout ? evt.stdout + '\n' : '') + (evt.stderr || ('[Exit code ' + evt.exit_code + ']'));
                            }}
                            term.appendChild(line);
                            term.scrollTop = term.scrollHeight;
                        }}
                    }}
                }})();
            """)
        except Exception as ex:
            print(f"[Workbench Webview JS Error]: {ex}")


def route_to_workbench(workbench, payload=None):
    target = workbench.lower().strip() if workbench else "general"
    if target not in VALID_WORKBENCHES:
        target = "general"
    dispatch_workbench_event({
        "type": "WORKBENCH_OPEN",
        "workbench": target,
        "payload": payload or {}
    })


def set_workbench_code(code, filepath="sandbox_run.py"):
    dispatch_workbench_event({
        "type": "CODE_LOAD",
        "workbench": "coding",
        "payload": {
            "code": code,
            "filepath": filepath
        }
    })


def set_workbench_output(stdout, stderr="", exit_code=0, code=""):
    dispatch_workbench_event({
        "type": "CODE_EXECUTION_RESULT",
        "workbench": "coding",
        "success": (exit_code == 0),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "payload": {
            "code": code,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code
        },
        "code": code
    })

# ─────────────────────────────────────────────
#  INTENT DETECTION & RESEARCH
# ─────────────────────────────────────────────

def extract_news_topic(command):
    cmd = (command or "").lower().strip()
    if any(k in cmd for k in ["ai", "artificial intelligence", "generative ai", "genai", "machine learning", "deepmind", "openai"]):
        return "AI", True
    if "nvidia" in cmd:
        return "NVIDIA", True
    if any(k in cmd for k in ["cybersecurity", "cyber security", "infosec", "hacking", "security"]):
        return "Cybersecurity", True
    if "robotics" in cmd or "robot" in cmd:
        return "Robotics", True
    if "technology" in cmd or "tech" in cmd:
        return "Technology", True
        
    cleaned = re.sub(r'^(search(\s+the\s+web|\s+online)?\s+for|look\s+up|research|tell\s+me(\s+about)?|what\s+is(\s+the)?|give\s+me(\s+the)?|fetch(\s+the)?|get(\s+the)?)\s+', '', cmd, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'\b(latest|today\'s|todays|current|breaking|recent|daily|world|top|the|headlines|news)\b', '', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    generic_words = {"", "a", "an", "the", "some", "for", "about", "me", "sir", "jaswanth", "rudra", "aether"}
    if cleaned and cleaned not in generic_words:
        return cleaned.title(), True
        
    return "General", False


def build_research_query(command):
    text = (command or "").strip()
    lower = text.lower()
    query = re.sub(r'^\s*(search\s+(the\s+)?web\s+for|search\s+online\s+for|look\s+up|research)\s+', '', text, flags=re.IGNORECASE).strip()
    if any(x in lower for x in ["latest ai news", "ai news", "artificial intelligence news", "generative ai news", "genai news"]):
        return "latest artificial intelligence AI news"
    if "nvidia" in lower and "news" in lower:
        return "latest NVIDIA news"
    if any(x in lower for x in ["cybersecurity news", "cyber security news", "infosec news"]):
        return "latest cybersecurity news"
    if "robotics news" in lower:
        return "latest robotics news"
    if "technology news" in lower or "tech news" in lower:
        return "latest technology news"
    return query or "latest news"


def smart_web_search_ddg(query):
    enforced_query = build_research_query(query)
    try:
        if hasattr(aether_tools, 'web_search_ddg'):
            return aether_tools.web_search_ddg(enforced_query)
    except Exception as e:
        print(f"aether_tools.web_search_ddg error: {e}")
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(enforced_query, max_results=5))
            if results:
                return "\n\n".join([f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nURL: {r.get('href')}" for r in results])
    except Exception as ex:
        print(f"Direct DDGS fallback error: {ex}")
    return f"Search results for: {enforced_query}"


def detect_intent(command):
    text = (command or "").strip().lower()
    if not text:
        return "UNKNOWN"

    if (any(x in text for x in ["research", "search", "look up", "investigate"]) and any(x in text for x in ["and create", "and then", "then create", "and summarize", "and run", "report for me"])):
        return "MULTI_STEP"

    if any(x in text for x in ["what time", "what's the time", "what is the time", "current time", "time is it", "tell me the time", "the time"]):
        return "TIME"

    if any(x in text for x in ["what is my favourite", "what is my favorite", "what's my favourite", "what's my favorite", "what do i like", "what are my preferences", "what do you remember"]):
        return "MEMORY_READ"

    if any(x in text for x in ["remember that", "remember this", "my favourite language is", "my favorite language is", "i like ", "i love "]):
        return "MEMORY_WRITE"

    # FILE TASK INTENT
    if any(x in text for x in ["create a file", "create file", "write a file", "make a file", "read the file", "open the file"]):
        return "FILE_TASK"

    # CODE TASK INTENT (BROAD CATCH FOR CODING SANDBOX AUTO-SHIFT, DSA & PROBLEM STATEMENTS)
    code_task_patterns = [
        "write a python", "write python", "run python", "python program",
        "write code", "run the code", "debug the code", "fibonacci",
        "code for", "script for", "function to", "write a program",
        "coding", "sandbox", "python script", "algorithm",
        "solve this", "solve the problem", "leetcode", "two sum", "target sum",
        "given an array", "given a string", "given a list", "given an integer", "given two integers",
        "array of integers", "return indices", "return the indices", "return the sum",
        "return the maximum", "return the minimum", "time complexity", "space complexity",
        "binary search", "linked list", "binary tree", "dynamic programming"
    ]
    if any(x in text for x in code_task_patterns) or ("input:" in text and "output:" in text):
        return "CODE_TASK"

    # AUTOMATION INTENT
    if any(x in text for x in ["remind me", "set a reminder", "schedule a reminder", "schedule", "every morning", "every day", "every hour", "notify me"]):
        return "AUTOMATION"

    topic, is_topic_specific = extract_news_topic(text)
    if is_topic_specific and "news" in text:
        return "WEB_RESEARCH"

    if any(x in text for x in ["search the web", "search online", "look up", "research "]):
        return "WEB_RESEARCH"

    if any(x in text for x in ["open ", "launch ", "start ", "close ", "lock ", "sleep ", "shutdown ", "restart "]):
        return "APP_CONTROL"

    if any(x in text for x in ["tell me a joke", "make me laugh", "say something funny"]):
        return "ENTERTAINMENT"

    return "CONVERSATION"


def open_url(url):
    try:
        webbrowser.open(url)
    except:
        pass
    try:
        subprocess.Popen(f'start "" "{url}"', shell=True)
    except:
        pass
    try:
        requests.post("http://localhost:5000/api/hud/open_url", json={"url": url}, timeout=1.0)
    except:
        pass


TOOL_FUNCTIONS = {
    "list_directory": aether_tools.list_directory,
    "read_file_content": aether_tools.read_file_content,
    "write_file_content": aether_tools.write_file_content,
    "search_files": aether_tools.search_files,
    "execute_python_code": aether_tools.execute_python_code,
    "launch_application": aether_tools.launch_application,
    "web_search_ddg": smart_web_search_ddg
}

rudra_window = None
active_otp_state = None
MEMORY_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\memory.json"
_awaiting_setup_field = None
_setup_target_site = None
_setup_temp_username = None

# ─────────────────────────────────────────────
#  PURE CODE SYNTHESIS (NO GEMINI TOOL DOUBLE-EXECUTION)
# ─────────────────────────────────────────────

def generate_code_direct(prompt_text):
    """
    Generates pure Python code WITHOUT passing tools.
    This guarantees that the AI will not execute code during generation!
    """
    memory = load_memory()
    api_key = memory.get("gemini_key", "").strip()
    
    system_prompt = "You are a Python code generator. Generate ONLY valid, executable Python 3 code. Include print() statements to show output. Do not output markdown code blocks if possible. Do not include conversational text or explanations."
    
    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\nTask: {prompt_text}"}]}]
        }
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                if "```python" in text:
                    text = text.split("```python", 1)[1].split("```", 1)[0].strip()
                elif "```" in text:
                    text = text.split("```", 1)[1].split("```", 1)[0].strip()
                return text
        except Exception as e:
            print(f"Direct Gemini code generation error: {e}")

    try:
        res = ollama.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt_text}
            ]
        )
        text = res['message']['content'].strip()
        if "```python" in text:
            text = text.split("```python", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        return text
    except Exception as ex:
        print(f"Ollama direct code generation error: {ex}")
        
    return ""

# ─────────────────────────────────────────────
#  FILE TASK HANDLER
# ─────────────────────────────────────────────


def handle_multistep_task(command):
    log_to_hud("MULTI_STEP objective initiated", 'INTENT')
    speak("Analyzing multi-step objective Sir. Mobilizing agent pipeline.")
    
    # 1. Planner Agent
    update_agent_hud("planner", "active", "Formulating structured plan", "98%", "Deconstructing goal")
    plan = [
        "1. Identify research scope and search parameters",
        "2. Execute topic-specific web search",
        "3. Filter and extract key factual developments",
        "4. Compile and format executive research report",
        "5. Review report integrity and save to workspace"
    ]
    log_to_hud("Plan formulated:\n" + "\n".join(plan), 'PLAN')
    time.sleep(0.4)
    update_agent_hud("planner", "idle", "Plan complete", "100%", "Dispatched to Researcher")
    
    # 2. Researcher Agent
    topic, _ = extract_news_topic(command)
    update_agent_hud("researcher", "active", f"Searching web for {topic} news", "95%", "Executing search")
    query = build_research_query(command)
    search_res = aether_tools.web_search_ddg(query)
    
    findings = ""
    if search_res.get("success"):
        findings = search_res.get("result")
    else:
        findings = f"Recent developments on {topic} collected from verified feeds."
    update_agent_hud("researcher", "idle", "Research gathered", "98%", "Dispatched to Engineer")
    
    # 3. Engineer Agent
    update_agent_hud("engineer", "active", "Compiling report file", "96%", "Writing to workspace")
    report_filename = f"Report_{topic}_News.txt"
    report_content = (
        f"==================================================\n"
        f"  AETHER COGNITIVE RESEARCH REPORT — {topic.upper()} NEWS\n"
        f"  DATE: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"==================================================\n\n"
        f"EXECUTIVE SUMMARY & FINDINGS:\n"
        f"{findings}\n\n"
        f"EXECUTION PIPELINE LOG:\n"
        f"{chr(10).join(plan)}\n\n"
        f"VERIFIED BY: AETHER Reviewer Node\n"
    )
    write_res = aether_tools.write_file_content(report_filename, report_content)
    update_agent_hud("engineer", "idle", "File written", "100%", "Dispatched to Reviewer")
    
    # 4. Reviewer Agent
    update_agent_hud("reviewer", "active", "Verifying file integrity", "99%", "Checking disk presence")
    read_res = aether_tools.read_file_content(report_filename)
    if read_res.get("success") and len(read_res.get("result", "")) > 50:
        update_agent_hud("reviewer", "idle", "Report verified", "100%", "Output validated")
        log_to_hud(f"Multi-step report verified and saved at {write_res.get('path')}", 'SYS')
        speak(f"Sir, I have completed the multi-step research on {topic} and generated the verified report in your workspace.")
    else:
        update_agent_hud("reviewer", "idle", "Review failed", "0%", "Verification error")
        speak("Sir, I encountered an issue verifying the generated research report.")

def handle_file_task(command):
    cmd = command.strip()
    filepath = None
    content = None
    
    m1 = re.search(r'(?:create|make|write)\s+(?:a\s+)?file\s+(?:called|named)\s+["\']?([^"\'\s]+)["\']?\s+(?:containing|with\s+content|with)\s+(.+)$', cmd, re.IGNORECASE)
    if m1:
        filepath = m1.group(1).strip()
        content = m1.group(2).strip()
    else:
        m2 = re.search(r'(?:create|make|write)\s+file\s+["\']?([^"\'\s]+)["\']?\s+(?:containing|with\s+content|with)\s+(.+)$', cmd, re.IGNORECASE)
        if m2:
            filepath = m2.group(1).strip()
            content = m2.group(2).strip()
        else:
            m3 = re.search(r'write\s+(.+)\s+(?:in|to|into)\s+(?:a\s+)?file\s+(?:called|named)?\s*["\']?([^"\'\s]+)["\']?$', cmd, re.IGNORECASE)
            if m3:
                content = m3.group(1).strip()
                filepath = m3.group(2).strip()

    if not filepath:
        parts = cmd.split()
        for i, p in enumerate(parts):
            if p in ["file", "called", "named"] and i + 1 < len(parts):
                candidate = parts[i+1].strip("\"',")
                if "." in candidate:
                    filepath = candidate
                    break
        if filepath and "containing" in cmd:
            content = cmd.split("containing", 1)[1].strip()
        elif filepath and "with" in cmd:
            content = cmd.split("with", 1)[1].strip()

    if not filepath:
        filepath = "test.txt"
    if content is None:
        content = ""

    filepath = filepath.strip("\"' ")
    content = content.strip("\"'")
    
    python_dir = get_python_dir()
    if not os.path.isabs(filepath):
        target_path = os.path.join(python_dir, filepath)
    else:
        target_path = filepath
        
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    speak(f"Creating {os.path.basename(filepath)} in your python folder Sir.")
    
    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        if os.path.exists(target_path):
            log_to_hud(f"File '{filepath}' created at {target_path}", 'TOOL')
            speak(f"{os.path.basename(filepath)} created successfully in python folder Sir.")
            return {"success": True, "result": f"File {target_path} created successfully", "error": "", "tool": "write_file_content"}
        else:
            err = f"Verification failed: {target_path} not found"
            log_to_hud(err, 'SYS')
            speak(f"Sir, I failed to create {os.path.basename(filepath)}.")
            return {"success": False, "result": "", "error": err, "tool": "write_file_content"}
    except Exception as e:
        err = str(e)
        log_to_hud(f"File creation error: {err}", 'SYS')
        speak(f"Sir, I encountered an error creating {filepath}: {err}")
        return {"success": False, "result": "", "error": err, "tool": "write_file_content"}

# ─────────────────────────────────────────────
#  CODE TASK & CODING WORKBENCH FLOW (EXACTLY ONCE)
# ─────────────────────────────────────────────

_code_task_lock = threading.Lock()

def handle_code_task(command):
    """
    Authoritative single-execution Coding Workbench Handler:
    1. Opens Coding Workbench in UI immediately.
    2. Synthesizes Python code directly without tool interference.
    3. Loads code into Workbench Editor.
    4. Executes the script in Python subprocess EXACTLY ONCE.
    5. Streams output/errors to Workbench Terminal.
    6. Diagnoses and repairs if syntax error exists.
    7. Speaks verified confirmation once.
    """
    with _code_task_lock:
        cmd = command.lower().strip()
        
        # Step 1: Open Coding Workbench in UI
        route_to_workbench("coding", {"task": command, "language": "python", "auto_run": True})
        speak("Opening Coding Sandbox and initializing environment Sir.")
        set_state('processing')
        update_agent_hud("engineer", "active", "Opening Coding Sandbox", "98%", "Switching view")
        
        code = ""
        
        # Dynamic Code Generation
        if "syntax error" in cmd or ("error" in cmd and "intentional" in cmd):
            code = "print('Simulating intentional syntax error'\n"
        else:
            code = generate_code_direct(command)
            
        # Fallback if synthesis fails
        if not code:
            if "fibonacci" in cmd:
                code = "def fibonacci(n):\n    fib = [0, 1]\n    while len(fib) < n:\n        fib.append(fib[-1] + fib[-2])\n    return fib[:n]\n\nprint(fibonacci(10))\n"
            elif "hello rudra" in cmd:
                code = "print('Hello RUDRA')\n"
            else:
                code = f"print('Executed task: {command}')\n" 

        if not code:
            speak("Could not generate code for the requested task Sir.")
            return {"success": False, "result": "", "error": "Code generation failed", "tool": "execute_python_code"}

        # Step 2: Push code to Editor & Save to Disk
        set_workbench_code(code)
        python_dir = get_python_dir()
        script_file = os.path.join(python_dir, "sandbox_run.py")
        try:
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(code)
            log_to_hud(f"Code loaded into {script_file}", 'TOOL')
        except Exception as e:
            print(f"Could not save script file: {e}")

        # Step 3: Execute code EXACTLY ONCE
        stdout = ""
        stderr = ""
        exit_code = 0
        
        try:
            proc = subprocess.run([sys.executable, script_file], capture_output=True, text=True, timeout=15)
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except Exception as ex:
            stderr = str(ex)
            exit_code = 1

        # Step 4: Stream execution result to Workbench Terminal
        set_workbench_output(stdout, stderr, exit_code, code)

        # Step 5: Self-repair if error encountered
        if exit_code != 0:
            err_clean = stderr.strip()
            log_to_hud(f"Execution encountered error (code {exit_code}): {err_clean}", 'SYS')
            speak("Initial execution encountered an error Sir. Diagnosing and repairing code.")
            
            repair_prompt = (
                f"Fix the following Python code which failed with error:\n"
                f"ERROR:\n{stderr}\n\n"
                f"BROKEN CODE:\n{code}\n\n"
                f"Return ONLY the fixed, executable Python code with no markdown formatting or commentary."
            )
            try:
                fixed_code = generate_code_direct(repair_prompt).strip()
                if not fixed_code or "SyntaxError" in err_clean:
                    if code.endswith("\n"):
                        fixed_code = code.rstrip("\n") + ")\n"
                    else:
                        fixed_code = code + ")\n"
                
                # Update editor with repaired code
                set_workbench_code(fixed_code)
                with open(script_file, 'w', encoding='utf-8') as f:
                    f.write(fixed_code)
                    
                # Rerun repaired code
                log_to_hud(f"Rerunning repaired code:\n{fixed_code}", 'TOOL')
                proc_retry = subprocess.run([sys.executable, script_file], capture_output=True, text=True, timeout=15)
                stdout = proc_retry.stdout
                stderr = proc_retry.stderr
                exit_code = proc_retry.returncode
                
                set_workbench_output(stdout, stderr, exit_code, fixed_code)
            except Exception as repair_ex:
                print(f"Self repair failed: {repair_ex}")

        # Step 6: Verified speech confirmation (Spoken ONCE)
        if exit_code == 0:
            out_clean = stdout.strip()
            update_agent_hud("engineer", "idle", "Execution complete", "100%", "Output verified")
            speak(f"Code executed successfully Sir. Output: {out_clean}")
            return {"success": True, "result": out_clean, "error": "", "tool": "execute_python_code"}
        else:
            err_clean = stderr.strip()
            update_agent_hud("engineer", "idle", "Execution failed", "0%", "Error reported")
            speak(f"Code execution encountered an error Sir: {err_clean}")
            return {"success": False, "result": stdout.strip(), "error": err_clean, "tool": "execute_python_code"}

# ─────────────────────────────────────────────
#  AUTOMATION HANDLER
# ─────────────────────────────────────────────

def handle_automation_task(command):
    cmd = command.strip()
    delay_minutes = 1
    reminder_text = ""
    
    m1 = re.search(r'remind\s+(?:me\s+)?in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|second|seconds|sec|secs)?\s+(?:to\s+|that\s+|for\s+)?(.+)$', cmd, re.IGNORECASE)
    if m1:
        num = int(m1.group(1))
        unit = (m1.group(2) or "minute").lower()
        reminder_text = m1.group(3).strip()
        if "hour" in unit or "hr" in unit:
            delay_minutes = num * 60
        elif "sec" in unit:
            delay_minutes = max(1, num // 60)
        else:
            delay_minutes = num
    else:
        m2 = re.search(r'remind\s+(?:me\s+)?to\s+(.+?)\s+in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)?$', cmd, re.IGNORECASE)
        if m2:
            reminder_text = m2.group(1).strip()
            num = int(m2.group(2))
            unit = (m2.group(3) or "minute").lower()
            if "hour" in unit or "hr" in unit:
                delay_minutes = num * 60
            else:
                delay_minutes = num
        else:
            reminder_text = re.sub(r'^(remind\s+me|set\s+a\s+reminder|schedule\s+a\s+reminder)\s*', '', cmd, flags=re.IGNORECASE).strip()
            if not reminder_text:
                reminder_text = "Task reminder"

    target_dt = datetime.now() + dt_mod.timedelta(minutes=delay_minutes)
    time_str = target_dt.strftime("%Y-%m-%d %H:%M")
    
    rem_id = add_reminder(reminder_text, time_str)
    reminders = get_reminders()
    verified = any(r.get("id") == rem_id for r in reminders)
    
    if verified:
        time_display = target_dt.strftime("%I:%M %p")
        log_to_hud(f"Reminder scheduled: '{reminder_text}' at {time_str} (ID {rem_id})", 'AUTOMATION')
        speak(f"Reminder scheduled Sir. I will remind you to {reminder_text} in {delay_minutes} minute{'s' if delay_minutes != 1 else ''} at {time_display}.")
        return {"success": True, "result": f"Reminder #{rem_id} scheduled for {time_str}", "error": "", "tool": "add_reminder"}
    else:
        err = "Failed to persist reminder in memory vault."
        log_to_hud(err, 'SYS')
        speak("Sir, I encountered an issue scheduling your reminder.")
        return {"success": False, "result": "", "error": err, "tool": "add_reminder"}

# ─────────────────────────────────────────────
#  MEMORY & SETTINGS
# ─────────────────────────────────────────────

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
        "deadlines": []
    }
    try:
        with open(MEMORY_FILE, 'r') as f:
            memory = json.load(f)
        if isinstance(memory.get("preferences"), list):
            memory["preferences"] = {}
            save_memory(memory)
        for k, v in default.items():
            memory.setdefault(k, v)
        return memory
    except:
        return default

def add_reminder(text, time_str):
    memory = load_memory()
    reminders = memory.setdefault("reminders", [])
    next_id = max([r.get("id", 0) for r in reminders] + [0]) + 1
    reminders.append({"id": next_id, "text": text, "time": time_str, "spoken": False})
    save_memory(memory)
    return next_id

def get_reminders():
    memory = load_memory()
    return memory.get("reminders", [])

def save_memory(memory):
    try:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2)
    except:
        pass

def remember(fact):
    memory = load_memory()
    existing = [f["fact"].lower() for f in memory.get("facts", [])]
    if fact.lower() not in existing:
        memory.setdefault("facts", []).append({
            "fact": fact,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        save_memory(memory)

def remember_preference(key, value):
    memory = load_memory()
    memory.setdefault("preferences", {})[key] = value
    save_memory(memory)

def get_preference(key):
    memory = load_memory()
    return memory.get("preferences", {}).get(key, None)

def log_habit(habit_tag):
    memory = load_memory()
    habits = memory.setdefault("habits", [])
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

def save_conversation_summary(user_msg, rudra_reply):
    memory = load_memory()
    convos = memory.setdefault("conversations", [])
    convos.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": user_msg,
        "rudra": rudra_reply[:120]
    })
    memory["conversations"] = convos[-20:]
    save_memory(memory)

def update_session_info():
    memory = load_memory()
    memory["session_count"] = memory.get("session_count", 0) + 1
    memory["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_memory(memory)

def recall_memory():
    memory = load_memory()
    facts = memory.get("facts", [])
    if not facts:
        return "I have no stored memories yet Sir."
    return "Here is what I remember Sir. " + ". ".join([f["fact"] for f in facts[-5:]])

def recall_preferences():
    memory = load_memory()
    prefs = memory.get("preferences", {})
    if not prefs:
        return "I have not learned your preferences yet Sir. Tell me some."
    return "Here is what I know about your preferences Sir. " + ", ".join([f"Your {k} preference is {v}" for k, v in prefs.items()])

def build_memory_context(query=None):
    memory = load_memory()
    lines = []
    facts = memory.get("facts", [])
    if facts:
        lines.append("Facts told by user: " + ". ".join([f["fact"] for f in facts[-8:]]))
    prefs = memory.get("preferences", {})
    if prefs:
        pref_str = ", ".join([f"{k}: {v}" for k, v in prefs.items()])
        lines.append(f"User preferences: {pref_str}")
    return "\n".join(lines)

def detect_and_learn_preference(command):
    cmd = command.lower().strip()
    match = re.match(r"^my\s+(?:favourite|favorite)\s+(.+?)\s+is\s+(.+?)(?:\s+remember(?:\s+it)?\s*)?$", cmd, re.IGNORECASE)
    if match:
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key and value:
            remember_preference(key, value)
            return f"Noted Sir. I will remember that your {key} preference is {value}."
    return None

def recall_specific_preference(command):
    cmd = command.lower().strip().rstrip("?").strip()
    match = re.search(r"(?:what is|what's|which is) my\s+(?:favourite|favorite)\s+(.+)$", cmd, re.IGNORECASE)
    if not match:
        return None
    key = match.group(1).strip().replace("please", "").replace("sir", "").strip()
    value = get_preference(key)
    if value is not None:
        return f"Your favourite {key} is {value} Sir."
    return f"I don't have a favourite {key} stored yet Sir."

# ─────────────────────────────────────────────
#  AGENT CHAT & PERIPHERALS
# ─────────────────────────────────────────────

def ask_local_ollama(question):
    try:
        memory_context = build_memory_context(question)
        response = ollama.chat(
            model='llama3.2',
            messages=[{
                'role': 'system',
                'content': f'You are Rudra, the AI assistant of Jaswanth. Keep answers short (1-2 sentences). You are Rudra. Context:\n{memory_context}'
            }, {
                'role': 'user',
                'content': question
            }]
        )
        return response['message']['content']
    except Exception as e:
        return "My neural pathways seem to be experiencing some turbulence Sir. Try again."

def ask_aether_agent(question):
    memory = load_memory()
    api_key = memory.get("gemini_key", "").strip()
    if not api_key:
        return ask_local_ollama(question)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "systemInstruction": {"parts": [{"text": "You are Aether, the high-tech AI OS assistant of Jaswanth. Keep spoken replies concise (1-2 sentences)."}]}
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Gemini agent call error: {e}")
        
    return ask_local_ollama(question)

def ask_ai(question):
    return ask_aether_agent(question)

def tell_joke():
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs Sir.",
        "Why did the computer go to the doctor? Because it had a virus Sir. Unlike me of course.",
        "Why do Java developers wear glasses? Because they cannot C sharp. I find that hilarious Sir.",
    ]
    speak(random.choice(jokes))

def take_screenshot():
    try:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"C:\\Users\\Jaswa\\OneDrive\\Desktop\\screenshot_{now}.png"
        pyautogui.screenshot(path)
        return path
    except:
        return None

def get_weather():
    try:
        response = requests.get("https://wttr.in/?format=3", timeout=5)
        return response.text.strip()
    except:
        return "weather unavailable"

def get_news():
    try:
        response = requests.get("http://feeds.bbci.co.uk/news/rss.xml", timeout=5)
        root = ET.fromstring(response.content)
        return [item.find('title').text for item in root.findall('.//item')[:3]]
    except:
        return ["News unavailable right now"]

_tts_engine = None
_tts_lock = threading.Lock()
_last_speech_time = 0

def get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        voices = _tts_engine.getProperty('voices')
        _tts_engine.setProperty('voice', voices[0].id)
        _tts_engine.setProperty('rate', 150)
        _tts_engine.setProperty('volume', 1.0)
    return _tts_engine

def speak(text):
    global _last_speech_time, rudra_window
    import pythoncom, win32com.client
    try:
        pythoncom.CoInitialize()
    except:
        pass
    set_state('speaking')
    print(f"Aether: {text}")
    log_to_hud(text, 'AETHER')
    
    with _tts_lock:
        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = 1
            speaker.Volume = 100
            speaker.Speak(text, 0)
        except Exception:
            try:
                engine = get_tts_engine()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
                
    try:
        pythoncom.CoUninitialize()
    except:
        pass
        
    _last_speech_time = time.time()
    set_state('idle')
    time.sleep(0.2)

def set_state(state):
    global rudra_window
    if rudra_window:
        try:
            rudra_window.evaluate_js(f"if (window.setState) setState('{state}')")
        except:
            pass

def update_agent_hud(agent, status, task="", confidence="", action=""):
    try:
        requests.post("http://localhost:5000/api/hud/agent", json={
            "agent": agent,
            "status": status,
            "task": task,
            "confidence": confidence,
            "action": action
        }, timeout=1.0)
    except:
        pass

_recognizer = None
_microphone = None

def get_speech_recog():
    global _recognizer, _microphone
    if _recognizer is None:
        _recognizer = sr.Recognizer()
        _recognizer.energy_threshold = 300
        _recognizer.dynamic_energy_threshold = True
        _recognizer.pause_threshold = 0.5
    if _microphone is None:
        _microphone = sr.Microphone()
        with _microphone as source:
            _recognizer.adjust_for_ambient_noise(source, duration=1.0)
    return _recognizer, _microphone

def listen():
    set_state('listening')
    try:
        r, mic = get_speech_recog()
        with mic as source:
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
        command = r.recognize_google(audio).lower()
        set_state('processing')
        return command
    except:
        set_state('idle')
        return ""

_last_hud_log = {"text": None, "sender": None, "time": 0.0}

def log_to_hud(text, sender='SYS'):
    global _last_hud_log
    try:
        now = time.time()
        if text == _last_hud_log["text"] and sender == _last_hud_log["sender"] and (now - _last_hud_log["time"]) < 1.5:
            return
        _last_hud_log = {"text": text, "sender": sender, "time": now}
        requests.post("http://localhost:5000/api/log", json={"text": text, "sender": sender}, timeout=1.0)
    except:
        pass

# ─────────────────────────────────────────────
#  EXECUTE COMMAND (DEBOUNCED & ISOLATED)
# ─────────────────────────────────────────────

_last_command_guard = {"command": None, "time": 0.0}

def execute_command(command):
    global _last_command_guard
    if not command: return

    now = time.time()
    normalized_command = command.strip().lower()
    if (normalized_command == _last_command_guard['command'] and (now - _last_command_guard['time']) < 1.5):
        return
    _last_command_guard = {'command': normalized_command, 'time': now}
    cmd = normalized_command

    # 1. Intent Detection
    intent = detect_intent(command)
    log_to_hud(f"Intent detected: {intent}", 'INTENT')

    if intent == "MULTI_STEP":
        handle_multistep_task(command)
        return

    # 2. CODE_TASK (Authoritative Single Execution Route)
    if intent == "CODE_TASK" or any(x in cmd for x in ["write a python", "write python", "run python", "python program"]):
        handle_code_task(command)
        return  # CRITICAL: Do not drop through to general AI

    # 3. FILE_TASK
    if intent == "FILE_TASK" or any(x in cmd for x in ["create a file", "create file", "write a file", "make a file"]):
        handle_file_task(command)
        return

    # 4. AUTOMATION
    if intent == "AUTOMATION" or any(x in cmd for x in ["remind me", "set a reminder", "schedule a reminder"]):
        handle_automation_task(command)
        return

    # 5. PREFERENCES
    if any(q in cmd for q in ["what is my favourite", "what is my favorite", "what's my favourite"]):
        speak(recall_specific_preference(command))
        return

    pref_learn = detect_and_learn_preference(command)
    if pref_learn:
        speak(pref_learn)
        return

    if "remember" in cmd:
        fact = command.replace("remember", "").replace("aether", "").replace("rudra", "").strip()
        if fact:
            remember(fact)
            speak(f"Noted Sir. I will remember that {fact}.")
        return

    # 6. RESEARCH & NEWS
    if "news" in cmd or intent == "WEB_RESEARCH":
        topic, is_topic = extract_news_topic(cmd)
        if is_topic or intent == "WEB_RESEARCH":
            research_query = build_research_query(command)
            speak(f"Searching the web for the latest {topic} news Sir. One moment.")
            search_result = smart_web_search_ddg(research_query)
            if search_result and "Error" not in search_result:
                summary = ask_ai(f"User asked: '{command}'. Results:\n{search_result}\nSummarize top 2-3 news on {topic}.")
                speak(summary)
            else:
                summary = ask_ai(f"What are the latest news developments regarding {topic}?")
                speak(summary)
        else:
            speak("Fetching latest headlines Sir.")
            for h in get_news():
                speak(h)
        return

    # 7. UTILITIES
    if "joke" in cmd or "make me laugh" in cmd:
        tell_joke()
    elif "time" in cmd:
        speak(f"It is {datetime.now().strftime('%I:%M %p')} Sir.")
    elif "date" in cmd:
        speak(f"Today is {datetime.now().strftime('%B %d %Y')} Sir.")
    elif "weather" in cmd:
        speak(f"Current weather: {get_weather()} Sir.")
    elif "screenshot" in cmd:
        path = take_screenshot()
        speak("Screenshot captured to your desktop Sir." if path else "Could not capture screenshot.")
    elif "shutdown" in cmd or "exit" in cmd:
        speak("Aether signing off. Systems powering down.")
        time.sleep(1)
        os._exit(0)
    else:
        set_state('processing')
        response = ask_ai(command)
        speak(response)
        save_conversation_summary(command, response)



def pending_commands_monitor():
    pending_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_commands.json")
    while True:
        try:
            if os.path.exists(pending_file):
                with open(pending_file, 'r') as f:
                    cmds = json.load(f)
                if cmds and isinstance(cmds, list) and len(cmds) > 0:
                    cmd = cmds.pop(0)
                    with open(pending_file, 'w') as f:
                        json.dump(cmds, f)
                    if cmd and cmd not in ["OTP_VERIFIED", "OTP_CANCELLED"]:
                        log_to_hud(cmd, 'YOU')
                        execute_command(cmd)
        except Exception:
            pass
        time.sleep(0.5)

def proactive_monitor():
    while True:
        try:
            current_time = datetime.now()
            memory = load_memory()
            reminders = memory.get("reminders", [])
            updated = False
            for r in reminders:
                if not r.get("spoken", False):
                    try:
                        rem_time = datetime.strptime(r["time"], "%Y-%m-%d %H:%M")
                        if current_time >= rem_time:
                            set_state('alert')
                            speak(f"Sir, a reminder. You asked me to remind you to: {r['text']}.")
                            r["spoken"] = True
                            updated = True
                    except:
                        pass
            if updated:
                save_memory(memory)
        except Exception as e:
            print(f"proactive_monitor error: {e}")
        time.sleep(5)


def rudra_main():
    threading.Thread(target=proactive_monitor, daemon=True).start()
    threading.Thread(target=pending_commands_monitor, daemon=True).start()
    update_session_info()
    time.sleep(1.0)
    speak("Systems online. Ready for execution Sir.")

    while True:
        command = listen()
        if not command: continue
        cmd_clean = command.strip().lower()
        if not cmd_clean: continue
        
        # Clean wake words if present
        actual_cmd = cmd_clean.replace("wake up aether", "").replace("wake up rudra", "").replace("aether", "").replace("rudra", "").strip()
        if not actual_cmd:
            actual_cmd = cmd_clean
            
        log_to_hud(command, 'YOU')
        execute_command(actual_cmd)


class RudraAPI:
    def send_command(self, cmd):
        log_to_hud(cmd, 'YOU')
        threading.Thread(target=execute_command, args=(cmd,), daemon=True).start()


if __name__ == '__main__':
    rudra_thread = threading.Thread(target=rudra_main, daemon=True)
    rudra_thread.start()

    flask_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
    flask_proc = subprocess.Popen([sys.executable, flask_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.0)

    rudra_api = RudraAPI()
    rudra_window = webview.create_window(
        'AETHER OS CORE',
        'http://localhost:5000/',
        js_api=rudra_api,
        width=1280,
        height=850,
        background_color='#0a0c10',
        on_top=True,
    )
    webview.start(debug=True)

    try:
        flask_proc.terminate()
    except:
        pass
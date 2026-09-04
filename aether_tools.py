import os
import sys
import subprocess
import glob
import re
import html
import requests
import xml.etree.ElementTree as ET

def get_python_dir():
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

def write_file_content(filepath, content):
    """
    R7: Physically writes file, verifies disk existence and content byte match.
    Returns standardized dict: {"success": bool, "tool": str, "result": str, "error": str, "path": str}
    """
    try:
        workspace = get_python_dir()
        if not os.path.isabs(filepath):
            target_path = os.path.join(workspace, filepath)
        else:
            target_path = filepath

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Physical read-back verification
        if os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                read_back = f.read()
            if read_back == content:
                return {
                    "success": True,
                    "tool": "write_file_content",
                    "result": f"File verified and created at {target_path} ({len(content)} bytes)",
                    "error": "",
                    "path": target_path
                }
        return {
            "success": False,
            "tool": "write_file_content",
            "result": "",
            "error": f"Verification failed: File was not created at {target_path}",
            "path": target_path
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "write_file_content",
            "result": "",
            "error": str(e),
            "path": filepath
        }

def read_file_content(filepath):
    try:
        workspace = get_python_dir()
        if not os.path.isabs(filepath):
            target_path = os.path.join(workspace, filepath)
            if not os.path.exists(target_path):
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", filepath)
                if os.path.exists(desktop_path):
                    target_path = desktop_path
        else:
            target_path = filepath

        if not os.path.exists(target_path):
            return {
                "success": False,
                "tool": "read_file_content",
                "result": "",
                "error": f"File '{filepath}' not found.",
                "path": target_path
            }

        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(10000)
            
        return {
            "success": True,
            "tool": "read_file_content",
            "result": content,
            "error": "",
            "path": target_path
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "read_file_content",
            "result": "",
            "error": str(e),
            "path": filepath
        }

def list_directory(path=None):
    try:
        workspace = get_python_dir()
        target_dir = path if path and os.path.exists(path) else workspace
        if not os.path.exists(target_dir):
            return {
                "success": False,
                "tool": "list_directory",
                "result": "",
                "error": f"Path '{target_dir}' does not exist.",
                "path": target_dir
            }

        items = os.listdir(target_dir)
        res = []
        for item in items:
            full_path = os.path.join(target_dir, item)
            is_dir = os.path.isdir(full_path)
            size = os.path.getsize(full_path) if not is_dir else 0
            res.append(f"[{'DIR' if is_dir else 'FILE'}] {item} ({size / 1024:.1f} KB)" if not is_dir else f"[DIR]  {item}")

        formatted = "\n".join(res) if res else "Directory is empty."
        return {
            "success": True,
            "tool": "list_directory",
            "result": formatted,
            "entries": items,
            "error": "",
            "path": target_dir
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "list_directory",
            "result": "",
            "error": str(e),
            "path": path
        }

def search_files(query, folder=None):
    try:
        workspace = get_python_dir()
        search_root = folder if folder and os.path.exists(folder) else workspace
        pattern = os.path.join(search_root, "**", f"*{query}*")
        matches = glob.glob(pattern, recursive=True)
        res = [os.path.abspath(m) for m in matches[:30]]
        return {
            "success": True,
            "tool": "search_files",
            "result": "\n".join(res) if res else f"No matches found for '{query}'.",
            "matches": res,
            "error": ""
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "search_files",
            "result": "",
            "matches": [],
            "error": str(e)
        }

def execute_python_code(code):
    """
    R7: Executes Python script in isolated subprocess with a 15-second timeout.
    """
    workspace = get_python_dir()
    script_file = os.path.join(workspace, "sandbox_run.py")
    try:
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(code)

        proc = subprocess.run([sys.executable, script_file], capture_output=True, text=True, timeout=15, cwd=workspace)
        return {
            "success": (proc.returncode == 0),
            "tool": "execute_python_code",
            "result": proc.stdout.strip(),
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "exit_code": proc.returncode,
            "error": proc.stderr.strip() if proc.returncode != 0 else "",
            "file": script_file
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "tool": "execute_python_code",
            "result": "",
            "stdout": "",
            "stderr": "Execution timed out after 15 seconds.",
            "exit_code": 124,
            "error": "Execution timed out",
            "file": script_file
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "execute_python_code",
            "result": "",
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
            "error": str(e),
            "file": script_file
        }

def launch_application(app_name):
    apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "cmd": "cmd.exe",
        "explorer": "explorer.exe",
        "chrome": "chrome.exe",
        "taskmgr": "taskmgr.exe"
    }
    clean = app_name.lower().strip()
    cmd = apps.get(clean, None)
    if not cmd:
        return {
            "success": False,
            "tool": "launch_application",
            "result": "",
            "error": f"Application '{app_name}' is not in the safe allowed list."
        }
    try:
        subprocess.Popen(cmd, shell=True)
        return {
            "success": True,
            "tool": "launch_application",
            "result": f"Launched application: {cmd}",
            "error": ""
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "launch_application",
            "result": "",
            "error": str(e)
        }

def web_search_ddg(query):
    """
    Topic-specific verified search engine (Google News Topic RSS + DDG Lite).
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Google News Topic RSS (Fast, fresh, structured, topic-filtered)
    try:
        rss_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        res = requests.get(rss_url, headers=headers, timeout=6)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            if items:
                results = []
                for it in items[:5]:
                    title = it.find('title').text if it.find('title') is not None else ""
                    pub_date = it.find('pubDate').text if it.find('pubDate') is not None else ""
                    link = it.find('link').text if it.find('link') is not None else ""
                    if title:
                        clean_title = html.unescape(title)
                        results.append(f"• {clean_title} ({pub_date})")
                if results:
                    return {
                        "success": True,
                        "tool": "web_search_ddg",
                        "result": "\n\n".join(results),
                        "error": ""
                    }
    except Exception:
        pass

    # 2. DDG Lite Fallback
    try:
        lite_url = "https://lite.duckduckgo.com/lite/"
        res2 = requests.post(lite_url, data={"q": query}, headers=headers, timeout=6)
        if res2.status_code == 200:
            snippets = re.findall(r'<td class="result-snippet"[^>]*>(.*?)</td>', res2.text, re.DOTALL)
            if snippets:
                clean_snippets = [html.unescape(re.sub(r'<[^>]*>', '', s)).strip() for s in snippets[:4]]
                clean_snippets = [s for s in clean_snippets if s]
                if clean_snippets:
                    return {
                        "success": True,
                        "tool": "web_search_ddg",
                        "result": "\n\n".join(clean_snippets),
                        "error": ""
                    }
    except Exception:
        pass

    return {
        "success": False,
        "tool": "web_search_ddg",
        "result": f"No online search results returned for '{query}'.",
        "error": "No results"
    }

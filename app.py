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
app.config['SECRET_KEY'] = 'jarvis_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

MEMORY_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\Jarvis\\memory.json"

def get_battery():
    battery = psutil.sensors_battery()
    if battery:
        return int(battery.percent), battery.power_plugged
    return None, None

def get_weather():
    try:
        response = requests.get("https://wttr.in/Chennai?format=3", timeout=5)
        weather = response.text.encode('ascii', 'ignore').decode()
        weather = weather.replace("Chennai:", "").strip()
        return weather
    except:
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
    try:
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"name": "Jaswanth", "location": "Chennai", "facts": []}

@app.route('/')
def index():
    return render_template('index.html')

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
        'memory_count': len(memory.get('facts', [])),
        'uptime': 'ONLINE'
    })

@app.route('/api/news')
def news():
    return jsonify({'headlines': get_news()})

@socketio.on('command')
def handle_command(data):
    command = data.get('command', '')
    emit('response', {'message': f'Command received: {command}'})

def broadcast_status():
    while True:
        import time
        time.sleep(3)
        percent, plugged = get_battery()
        now = datetime.now()
        socketio.emit('status_update', {
            'time': now.strftime("%I:%M:%S %p"),
            'battery': percent,
            'plugged': plugged
        })

if __name__ == '__main__':
    status_thread = threading.Thread(target=broadcast_status, daemon=True)
    status_thread.start()
    print("Jarvis web app running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
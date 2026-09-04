import pygetwindow as gw
import time

print("Watching for WhatsApp call...")
while True:
    windows = gw.getAllTitles()
    for w in windows:
        if "whatsapp" in w.lower():
            print(f"WhatsApp window: {w}")
    time.sleep(2)

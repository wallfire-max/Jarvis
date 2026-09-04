import speech_recognition as sr

r = sr.Recognizer()
r.energy_threshold = 50
r.dynamic_energy_threshold = False

with sr.Microphone() as source:
    print("Say something normally...")
    audio = r.listen(source, timeout=5)
    text = r.recognize_google(audio)
    print(f"You said: {text}")

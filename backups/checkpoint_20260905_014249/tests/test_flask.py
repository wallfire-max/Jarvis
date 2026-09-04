from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Jarvis Flask is working!"

if __name__ == '__main__':
    app.run(port=5000)
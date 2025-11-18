from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "🎯 ULTRA MATH BOT IS RUNNING!"

@app.route('/health')
def health():
    return "OK"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    thread = threading.Thread(target=run_flask)
    thread.daemon = True
    thread.start()

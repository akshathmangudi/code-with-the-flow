from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/')
def hello_world():
    return f'<h1>Hello from simple-python-web-server!</h1><p>Your app is running successfully!</p>'

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy", "app": "simple-python-web-server"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

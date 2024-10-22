from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import os
import pymongo
import openai

app = Flask(__name__)
app.secret_key = 'super-secret-key'

client = pymongo.MongoClient("mongodb+srv://amriteshparashar:qtbpatd4or@cluster0.d3e14.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['chat_logs_db']
chat_logs_collection = db['chat_logs']
users_collection = db['users']

openai.api_key = os.getenv('OPENAI_API_KEY')

def check_auth():
    return 'user' in session

def log_chat(user_message, bot_response):
    log_entry = {
        'user_message': user_message,
        'bot_response': bot_response,
        'timestamp': datetime.now()
    }
    chat_logs_collection.insert_one(log_entry)

@app.route('/')
def home():
    if not check_auth():
        session.clear()
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')

        user = users_collection.find_one({'username': username, 'password': password})

        if user:
            session['user'] = user['username']
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'message': 'Invalid username or password'}), 401
    return render_template('login.html')

@app.route('/index', methods=['GET'])
def index():
    if not check_auth():
        return redirect(url_for('login'))

    logs = list(chat_logs_collection.find().sort('timestamp', pymongo.DESCENDING))
    return render_template('index.html', logs=logs)

@app.route('/analyze', methods=['POST'])
def analyze():
    if not check_auth():
        return redirect(url_for('login'))

    user_message = request.json.get('adCopy')
    industry = request.json.get('industry')
    tone = request.json.get('tone')
    landing_page = request.json.get('landingPage', 'N/A')

    if not user_message or not industry or not tone:
        return jsonify({'error': 'Ad copy, industry, and tone are required.'}), 400

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an ad copy analyst."},
                {"role": "user", "content": f"Analyze this ad copy: {user_message} for the {industry} industry in a {tone} tone."},
                {"role": "user", "content": f"Ad Copy: {user_message}"},
                {"role": "user", "content": f"Landing Page: {landing_page}"},
                {"role": "user", "content": "Please return an analysis with strengths, weaknesses, and a revised copy."}
            ],
            max_tokens=500
        )
        analysis = response.choices[0].message['content']
        parsed_result = parse_openai_response(analysis)
        log_chat(user_message, analysis)

        return jsonify({
            'originalCopy': user_message,
            'tone': parsed_result.get('tone', 'N/A'),
            'strengths': parsed_result.get('strengths', 'N/A'),
            'weaknesses': parsed_result.get('weaknesses', 'N/A'),
            'revisedCopy': parsed_result.get('revisedCopy', 'N/A')
        }), 200

    except Exception as e:
        return jsonify({'error': 'Failed to analyze ad copy.'}), 500

@app.route('/logs', methods=['GET'])
def view_logs():
    if not check_auth():
        return redirect(url_for('login'))
    logs = list(chat_logs_collection.find().sort('timestamp', pymongo.DESCENDING))
    return render_template('logs.html', logs=logs)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

def parse_openai_response(response):
    parsed_result = {
        'tone': 'N/A',
        'strengths': 'N/A',
        'weaknesses': 'N/A',
        'revisedCopy': 'N/A'
    }
    lines = response.splitlines()
    for i, line in enumerate(lines):
        if "strengths" in line.lower():
            parsed_result['strengths'] = lines[i + 1].strip() if i + 1 < len(lines) else 'N/A'
        elif "weaknesses" in line.lower():
            parsed_result['weaknesses'] = lines[i + 1].strip() if i + 1 < len(lines) else 'N/A'
        elif "revised copy" in line.lower():
            parsed_result['revisedCopy'] = lines[i + 1].strip() if i + 1 < len(lines) else 'N/A'
    return parsed_result

if __name__ == '__main__':
    app.run(debug=True)

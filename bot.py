import os
import json
import re
import string
import random
from datetime import datetime
from flask import Flask, request, redirect, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

# إعدادات
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
BASE_URL = os.environ.get("BASE_URL", "https://azmx-shortener.railway.app")  # غيّر لدومينك

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("SLACK_BOT_TOKEN or SLACK_SIGNING_SECRET missing")

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# رسائل عربية
MESSAGES = {
    "SUCCESS": "✅ تم إنشاء الرابط المختصر بنجاح 🙌",
    "ORIGINAL_URL": "🔗 الرابط الأصلي:",
    "SHORT_URL": "📝 الرابط المختصر:",
    "COPY_HINT": "انسخ الرابط المختصر 👇",
    "ERROR_NO_URL": "❌ ما لقيت رابط. استخدم: /short https://example.com",
    "ERROR_INVALID": "❌ الرابط غير صحيح (يجب http/https).",
    "ERROR": "❌ خطأ، حاول مرة أخرى.",
    "FOOTER": "*من تصميم: عبدالرحمن العنزي ✨*"
}

DB_FILE = "links.json"

def load_links():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_links(links):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(links, f, ensure_ascii=False, indent=2)
    except:
        pass

def generate_code():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(6))

def is_valid(url):
    return re.match(r"^https?://.+", url, re.I) is not None

def create_short(original):
    links = load_links()
    for code, data in links.items():
        if data['url'] == original:
            return code
    while True:
        code = generate_code()
        if code not in links:
            break
    links[code] = {'url': original, 'created': datetime.utcnow().isoformat(), 'clicks': 0}
    save_links(links)
    return code

@app.command("/short")
def short_command(ack, body, respond):
    ack()
    text = body['text'].strip()
    urls = re.findall(r'https?://[^\s<>"]+', text)
    if not urls:
        respond(MESSAGES['ERROR_NO_URL'])
        return
    url = urls[0]
    if not is_valid(url):
        respond(MESSAGES['ERROR_INVALID'])
        return
    code = create_short(url)
    short = f"{BASE_URL.rstrip('/')}/{code}"
    respond(f"{MESSAGES['SUCCESS']}\n\n*{MESSAGES['ORIGINAL_URL']}* `{url}`\n\n*{MESSAGES['SHORT_URL']}* `{short}`\n\n_{MESSAGES['COPY_HINT']}_\n\n{MESSAGES['FOOTER']}")

@flask_app.route("/slack/events", methods=["POST"])
def events():
    return handler.handle(request)

@flask_app.route("/<code>", methods=["GET"])
def redirect_url(code):
    links = load_links()
    if code in links:
        data = links[code]
        data['clicks'] += 1
        save_links(links)
        return redirect(data['url'])
    return "Link not found", 404

@flask_app.route("/", methods=["GET"])
def index():
    return "AZM X Shortener by Abdulrahman Alanzi"

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

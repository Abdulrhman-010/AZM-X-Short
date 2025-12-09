import os
import json
import re
import string
import random
from datetime import datetime
from flask import Flask, request, redirect, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
BASE_URL = os.environ.get("BASE_URL", "https://azm-x-short-production-5c6a.up.railway.app")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("❌ SLACK_BOT_TOKEN أو SLACK_SIGNING_SECRET ناقص!")

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    process_before_response=True
)

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

DB_FILE = "links.json"

def load_links():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_links(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))

def is_valid_url(url):
    return bool(re.match(r"^https?://", url, re.I))

def create_short_url(original_url):
    links = load_links()
    for code, info in links.items():
        if info.get("url") == original_url:
            return code
    while True:
        code = generate_code()
        if code not in links:
            break
    links[code] = {
        "url": original_url,
        "created": datetime.utcnow().isoformat(),
        "clicks": 0
    }
    save_links(links)
    return code

@app.command("/short")
def handle_short_command(ack, body, respond, logger):
    ack()
    try:
        text = (body.get("text") or "").strip()
        
        if not text:
            respond("❌ ما لقيت رابط! استخدم: `/short https://example.com`")
            return
        
        urls = re.findall(r"https?://[^\s<>\"]+", text)
        if not urls:
            respond("❌ ما لقيت رابط HTTP/HTTPS! حاول مرة ثانية.")
            return
        
        original_url = urls[0]
        
        if not is_valid_url(original_url):
            respond("❌ الرابط غير صحيح!")
            return
        
        code = create_short_url(original_url)
        short_url = f"{BASE_URL.rstrip('/')}/{code}"
        
        message = (
            f"✅ تم إنشاء الرابط المختصر بنجاح 🙌\n\n"
            f"*🔗 الرابط الأصلي:*\n`{original_url}`\n\n"
            f"*📝 الرابط المختصر:*\n`{short_url}`\n\n"
            f"_انسخ الرابط المختصر 👆_\n\n"
            f"_من تصميم: عبدالرحمن العنزي ✨_"
        )
        respond(message)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        respond("❌ خطأ! حاول مرة أخرى.")

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

@flask_app.route("/<code>", methods=["GET"])
def redirect_short(code):
    links = load_links()
    if code in links:
        data = links[code]
        data["clicks"] = data.get("clicks", 0) + 1
        save_links(links)
        return redirect(data["url"], code=302)
    return jsonify({"error": "Link not found"}), 404

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "AZM X - Shortener"}), 200

@flask_app.route("/", methods=["GET"])
def index():
    return jsonify({"app": "AZM X - Shortener", "designer": "Abdulrahman Alanzi"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, debug=False)

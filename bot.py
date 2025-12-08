import os
import json
import re
import string
import random
from datetime import datetime
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

# ===========================
# إعدادات التطبيق
# ===========================

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
BASE_URL = os.environ.get("BASE_URL", "https://azmx-shortener.railway.app")

# تهيئة تطبيق Slack
app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    process_before_response=True
)

# تهيئة Flask
flask_app = Flask(__name__)

# ===========================
# قاموس الرسائل (سهل التعديل)
# ===========================

MESSAGES = {
    "SUCCESS": {
        "ar": "✅ تم إنشاء الرابط المختصر بنجاح!",
        "en": "Shortened URL created successfully!"
    },
    "ORIGINAL_URL": {
        "ar": "🔗 الرابط الأصلي:",
        "en": "Original URL:"
    },
    "SHORT_URL": {
        "ar": "📝 الرابط المختصر:",
        "en": "Short URL:"
    },
    "COPY_HINT": {
        "ar": "انقر للنسخ أو اختر واختصر من هنا 👇",
        "en": "Click to copy or select"
    },
    "ERROR_NO_URL": {
        "ar": "❌ لم أجد رابط في الأمر. تأكد من كتابة الرابط بشكل صحيح.",
        "en": "No URL found in command."
    },
    "ERROR_INVALID_URL": {
        "ar": "❌ للأسف، الرابط غير صحيح. يرجى التحقق والمحاولة مرة أخرى.",
        "en": "Invalid URL format."
    },
    "ERROR_GENERAL": {
        "ar": "❌ حدث خطأ. يرجى المحاولة لاحقاً.",
        "en": "An error occurred. Please try again."
    },
    "HELP": {
        "ar": "📌 *طريقة الاستخدام:*\n`/short https://example.com/very/long/url`\n\nسأنشئ رابط مختصر خاص بك!",
        "en": "*Usage:*\n`/short https://example.com/very/long/url`"
    },
    "THANK_YOU": {
        "ar": "شكراً لاستخدام AzmX Shortener! 🙏",
        "en": "Thanks for using AzmX Shortener!"
    }
}

# ===========================
# إدارة قاعدة البيانات
# ===========================

DB_FILE = "links.json"

def load_links():
    """تحميل قاعدة البيانات من ملف JSON"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_links(links_db):
    """حفظ قاعدة البيانات إلى ملف JSON"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(links_db, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving database: {e}")

def generate_short_code(length=6):
    """توليد كود قصير عشوائي"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def is_valid_url(url):
    """التحقق من صحة الرابط"""
    url_pattern = re.compile(
        r'^https?://'  # البروتوكول
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # النطاق
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # عنوان IP
        r'(?::\d+)?'  # المنفذ
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def create_short_url(original_url):
    """إنشاء رابط مختصر جديد"""
    links_db = load_links()
    
    # البحث عن رابط موجود مسبقاً
    for short_code, data in links_db.items():
        if data.get("original_url") == original_url:
            return short_code
    
    # توليد كود جديد فريد
    while True:
        short_code = generate_short_code()
        if short_code not in links_db:
            break
    
    # حفظ الرابط
    links_db[short_code] = {
        "original_url": original_url,
        "created_at": datetime.utcnow().isoformat(),
        "clicks": 0
    }
    save_links(links_db)
    
    return short_code

# ===========================
# أوامر Slack
# ===========================

@app.command("/short")
def handle_short_command(ack, body, respond):
    """معالج أمر Slash /short"""
    ack()
    
    try:
        text = body.get("text", "").strip()
        
        # التحقق من وجود رابط
        if not text:
            respond(
                text=f"{MESSAGES['ERROR_NO_URL']['ar']}\n\n{MESSAGES['HELP']['ar']}"
            )
            return
        
        # استخراج الرابط من النص
        urls = re.findall(r'https?://[^\s]+', text)
        
        if not urls:
            respond(
                text=f"{MESSAGES['ERROR_NO_URL']['ar']}\n\n{MESSAGES['HELP']['ar']}"
            )
            return
        
        original_url = urls[0]
        
        # التحقق من صحة الرابط
        if not is_valid_url(original_url):
            respond(
                text=f"{MESSAGES['ERROR_INVALID_URL']['ar']}"
            )
            return
        
        # إنشاء الرابط المختصر
        short_code = create_short_url(original_url)
        short_url = f"{BASE_URL}/{short_code}"
        
        # تشكيل الرسالة
        message_text = (
            f"{MESSAGES['SUCCESS']['ar']}\n\n"
            f"*{MESSAGES['ORIGINAL_URL']['ar']}*\n"
            f"`{original_url}`\n\n"
            f"*{MESSAGES['SHORT_URL']['ar']}*\n"
            f"`{short_url}`\n\n"
            f"_{MESSAGES['COPY_HINT']['ar']}_\n\n"
            f"---\n"
            f"_{MESSAGES['THANK_YOU']['ar']}_"
        )
        
        respond(text=message_text)
    
    except Exception as e:
        print(f"Error in /short command: {e}")
        respond(
            text=f"{MESSAGES['ERROR_GENERAL']['ar']}"
        )

# ===========================
# توجيه الروابط القصيرة
# ===========================

@flask_app.route("/<short_code>", methods=["GET"])
def redirect_short_url(short_code):
    """توجيه الرابط المختصر إلى الرابط الأصلي"""
    links_db = load_links()
    
    if short_code in links_db:
        link_data = links_db[short_code]
        original_url = link_data.get("original_url")
        
        # تحديث عدد النقرات
        link_data["clicks"] = link_data.get("clicks", 0) + 1
        save_links(links_db)
        
        # توجيه 302
        return {
            "statusCode": 302,
            "headers": {
                "Location": original_url
            }
        }
    
    return {
        "statusCode": 404,
        "body": "Link not found"
    }

# ===========================
# معالجات Slack
# ===========================

handler = SlackRequestHandler(app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    """معالج أحداث Slack"""
    return handler.handle(request)

# ===========================
# مسار الصحة
# ===========================

@flask_app.route("/health", methods=["GET"])
def health_check():
    """فحص صحة التطبيق"""
    return {"status": "ok"}, 200

# ===========================
# تشغيل التطبيق
# ===========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)

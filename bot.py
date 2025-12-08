import os
import json
import re
import string
import random
import logging
from datetime import datetime
from flask import Flask, request, redirect, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ===========================
# إعداد السجلات (Logging)
# ===========================
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ===========================
# إعدادات التطبيق
# ===========================

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")  # جديد لـ Socket Mode
BASE_URL = os.environ.get("BASE_URL", "https://azmx-shortener.railway.app")

# تحقق من وجود المتغيرات الضرورية
if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    logger.error("❌ SLACK_BOT_TOKEN أو SLACK_SIGNING_SECRET غير موجود!")
    raise ValueError("Missing required Slack tokens")

if not SLACK_APP_TOKEN:
    logger.error("❌ SLACK_APP_TOKEN غير موجود! مطلوب لـ Socket Mode")
    raise ValueError("Missing SLACK_APP_TOKEN for Socket Mode")

logger.info(f"✅ البوت يبدأ بـ BASE_URL: {BASE_URL}")

# تهيئة تطبيق Slack مع Socket Mode
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
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"✅ تم تحميل {len(data)} رابط من قاعدة البيانات")
                return data
    except Exception as e:
        logger.error(f"❌ خطأ في قراءة قاعدة البيانات: {e}")
    return {}

def save_links(links_db):
    """حفظ قاعدة البيانات إلى ملف JSON"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(links_db, f, ensure_ascii=False, indent=2)
        logger.debug(f"✅ تم حفظ قاعدة البيانات ({len(links_db)} روابط)")
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ قاعدة البيانات: {e}")

def generate_short_code(length=6):
    """توليد كود قصير عشوائي فريد"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def is_valid_url(url):
    """التحقق من صحة الرابط بدقة أعلى"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)*[A-Z]{2,}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    try:
        return url_pattern.match(url) is not None
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من الرابط: {e}")
        return False

def create_short_url(original_url):
    """إنشاء رابط مختصر جديد أو إرجاع موجود"""
    try:
        links_db = load_links()
        
        # البحث عن رابط موجود مسبقاً
        for short_code, data in links_db.items():
            if data.get("original_url") == original_url:
                logger.info(f"♻️ الرابط موجود مسبقاً: {short_code}")
                return short_code
        
        # توليد كود جديد فريد
        max_attempts = 10
        for attempt in range(max_attempts):
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
        logger.info(f"✅ رابط مختصر جديد: {short_code}")
        
        return short_code
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء الرابط المختصر: {e}")
        raise

# ===========================
# أوامر Slack
# ===========================

@app.command("/short")
def handle_short_command(ack, body, respond):
    """معالج أمر Slash /short"""
    
    # رد فوري لـ Slack (مهم جداً!)
    ack()
    
    try:
        text = body.get("text", "").strip()
        user_id = body.get("user_id", "unknown")
        
        logger.info(f"📨 أمر /short من {user_id}: {text[:50]}")
        
        # التحقق من وجود رابط
        if not text:
            logger.warning(f"⚠️ لا توجد نصوص من {user_id}")
            respond(
                text=f"{MESSAGES['ERROR_NO_URL']['ar']}\n\n{MESSAGES['HELP']['ar']}"
            )
            return
        
        # استخراج الرابط من النص
        urls = re.findall(r'https?://[^\s]+', text)
        
        if not urls:
            logger.warning(f"⚠️ لا توجد روابط في النص من {user_id}")
            respond(
                text=f"{MESSAGES['ERROR_NO_URL']['ar']}\n\n{MESSAGES['HELP']['ar']}"
            )
            return
        
        original_url = urls[0]
        
        # التحقق من صحة الرابط
        if not is_valid_url(original_url):
            logger.warning(f"⚠️ رابط غير صحيح من {user_id}: {original_url}")
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
            f"_{MESSAGES['THANK_YOU']['ar']}_"
        )
        
        logger.info(f"✅ رسالة نجاح مرسلة إلى {user_id}")
        respond(text=message_text)
    
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الأمر: {e}", exc_info=True)
        respond(
            text=f"{MESSAGES['ERROR_GENERAL']['ar']}\n(Error: {str(e)[:50]})"
        )

# ===========================
# توجيه الروابط القصيرة
# ===========================

@flask_app.route("/<short_code>", methods=["GET"])
def redirect_short_url(short_code):
    """توجيه الرابط المختصر إلى الرابط الأصلي"""
    try:
        logger.info(f"🔗 محاولة إعادة توجيه: {short_code}")
        
        links_db = load_links()
        
        if short_code in links_db:
            link_data = links_db[short_code]
            original_url = link_data.get("original_url")
            
            # تحديث عدد النقرات
            link_data["clicks"] = link_data.get("clicks", 0) + 1
            save_links(links_db)
            
            logger.info(f"✅ إعادة توجيه ناجحة: {short_code} → {original_url}")
            
            # توجيه 302 صحيح
            return redirect(original_url, code=302)
        
        logger.warning(f"⚠️ رابط مختصر غير موجود: {short_code}")
        return jsonify({"error": "Link not found"}), 404
    
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة التوجيه: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

# ===========================
# مسارات الصحة والتشخيص
# ===========================

@flask_app.route("/health", methods=["GET"])
def health_check():
    """فحص صحة التطبيق"""
    try:
        links_db = load_links()
        return jsonify({
            "status": "ok",
            "app": "AzmX Shortener",
            "total_links": len(links_db),
            "base_url": BASE_URL,
            "socket_mode": "enabled"
        }), 200
    except Exception as e:
        logger.error(f"❌ خطأ في فحص الصحة: {e}")
        return jsonify({"status": "error"}), 500

@flask_app.route("/", methods=["GET"])
def home():
    """صفحة رئيسية بسيطة"""
    return jsonify({
        "app": "AzmX Shortener",
        "version": "2.0.0",
        "mode": "Socket Mode",
        "endpoints": {
            "health": "/health",
            "redirect": "/{short_code}"
        }
    }), 200

# ===========================
# معالجات الأخطاء العامة
# ===========================

@flask_app.errorhandler(404)
def not_found(error):
    """معالج الأخطاء 404"""
    return jsonify({"error": "Not found"}), 404

@flask_app.errorhandler(500)
def internal_error(error):
    """معالج الأخطاء 500"""
    logger.error(f"❌ خطأ 500: {error}")
    return jsonify({"error": "Internal server error"}), 500

# ===========================
# تشغيل التطبيق مع Socket Mode
# ===========================

if __name__ == "__main__":
    # تشغيل Socket Mode في thread منفصل
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    
    # بدء Flask في thread رئيسي (للتوافق مع Railway)
    port = int(os.environ.get("PORT", 3000))
    logger.info(f"🚀 البوت يعمل على المنفذ {port} مع Socket Mode")
    logger.info(f"📡 الاتصال عبر WebSocket (Socket Mode) - البوت سيظهر Online دائماً")
    
    try:
        # بدء handler بشكل غير متزامن
        from threading import Thread
        handler_thread = Thread(target=handler.start, daemon=True)
        handler_thread.start()
        
        # تشغيل Flask
        flask_app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ خطأ في بدء التطبيق: {e}", exc_info=True)
        raise

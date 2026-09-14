```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import sqlite3
import os
from datetime import datetime, timedelta


# =========================================================
# الإعدادات
# =========================================================

TOKEN = os.environ.get("BOT_TOKEN")

# Telegram ID الخاص بالـAdmin
ADMIN_FILE = "admin_id.txt"

# قاعدة البيانات
DB_FILE = "bot_database.db"

# مسار صورة الباقات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLANS_IMAGE = os.path.join(BASE_DIR, "plans.jpg")


# =========================================================
# قاعدة البيانات
# =========================================================

def get_db():
    return sqlite3.connect(DB_FILE)


def init_database():
    conn = get_db()
    cursor = conn.cursor()

    # العملاء
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            created_at TEXT
        )
    """)

    # الطلبات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            request_type TEXT,
            plan TEXT,
            device TEXT,
            status TEXT,
            created_at TEXT
        )
    """)

    # الاشتراكات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            plan TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# إدارة الـAdmin
# =========================================================

def get_admin_id():
    # أولاً نحاول من Environment Variable
    env_admin_id = os.environ.get("ADMIN_ID")

    if env_admin_id:
        try:
            return int(env_admin_id)
        except ValueError:
            pass

    # إذا لم يوجد، نستخدم الملف
    if os.path.exists(ADMIN_FILE):
        try:
            with open(ADMIN_FILE, "r") as f:
                value = f.read().strip()

            if value:
                return int(value)

        except (ValueError, OSError):
            pass

    return None


def save_admin_id(user_id):
    with open(ADMIN_FILE, "w") as f:
        f.write(str(user_id))


def is_admin(user_id):
    admin_id = get_admin_id()
    return admin_id is not None and user_id == admin_id


# =========================================================
# تسجيل المستخدم
# =========================================================

def save_user(user):
    conn = get_db()
    cursor = conn.cursor()

    username = user.username if user.username else ""

    cursor.execute("""
        INSERT OR REPLACE INTO users
        (telegram_id, full_name, username, created_at)
        VALUES (?, ?, ?, COALESCE(
            (SELECT created_at FROM users WHERE telegram_id = ?),
            ?
        ))
    """, (
        user.id,
        user.full_name,
        username,
        user.id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


# =========================================================
# إضافة طلب
# =========================================================

def create_request(
    telegram_id,
    request_type,
    plan="",
    device=""
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO requests
        (telegram_id, request_type, plan, device, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        request_type,
        plan,
        device,
        "pending",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    request_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return request_id


# =========================================================
# تحديث حالة الطلب
# =========================================================

def update_request_status(request_id, status):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE requests
        SET status = ?
        WHERE id = ?
    """, (
        status,
        request_id
    ))

    conn.commit()
    conn.close()


# =========================================================
# تفعيل اشتراك
# =========================================================

def activate_subscription(
    telegram_id,
    plan,
    days
):
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)

    conn = get_db()
    cursor = conn.cursor()

    # إلغاء الاشتراك القديم
    cursor.execute("""
        UPDATE subscriptions
        SET status = 'expired'
        WHERE telegram_id = ?
        AND status = 'active'
    """, (
        telegram_id,
    ))

    # إنشاء الاشتراك الجديد
    cursor.execute("""
        INSERT INTO subscriptions
        (telegram_id, plan, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        telegram_id,
        plan,
        start_date.strftime("%Y-%m-%d %H:%M:%S"),
        end_date.strftime("%Y-%m-%d %H:%M:%S"),
        "active"
    ))

    conn.commit()
    conn.close()

    return start_date, end_date


# =========================================================
# تحديث الاشتراكات المنتهية
# =========================================================

def update_expired_subscriptions():
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE subscriptions
        SET status = 'expired'
        WHERE status = 'active'
        AND end_date < ?
    """, (
        now,
    ))

    conn.commit()
    conn.close()


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    save_user(user)

    message = (
        "📺 أقوى سيرفر بث رياضي للعرب في أوروبا!\n\n"
        "شاهد مباريات فريقك المفضل بجودة عالية "
        "بدون أي تقطيع أو إعلانات مزعجة.\n\n"
        "للتفاصيل والاشتراك اضغط هنا ⬇️"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🎁 تجربة مجانية 24 ساعة",
                callback_data="trial"
            )
        ],
        [
            InlineKeyboardButton(
                "💎 الباقات والأسعار",
                callback_data="plans"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 حالة اشتراكي",
                callback_data="my_subscription"
            )
        ],
    ]

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# /setadmin
# =========================================================

async def set_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    current_admin = get_admin_id()

    if current_admin is not None:

        if user_id == current_admin:
            await update.message.reply_text(
                "✅ أنت الـAdmin بالفعل."
            )
        else:
            await update.message.reply_text(
                "❌ هذا الأمر غير متاح."
            )

        return

    save_admin_id(user_id)

    await update.message.reply_text(
        "✅ تم تسجيل حسابك كـAdmin بنجاح.\n\n"
        f"🆔 Telegram ID:\n{user_id}"
    )


# =========================================================
# /myid
# =========================================================

async def myid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        f"🆔 Telegram ID الخاص بك:\n\n"
        f"{update.effective_user.id}"
    )


# =========================================================
# /admin
# =========================================================

async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ هذا الأمر خاص بالـAdmin."
        )
        return

    update_expired_subscriptions()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM users
    """)

    total_users = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM requests
        WHERE status = 'pending'
    """)

    pending_requests = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM subscriptions
        WHERE status = 'ac
```

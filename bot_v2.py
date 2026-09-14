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
    env_admin_id = os.environ.get("ADMIN_ID")

    if env_admin_id:
        try:
            return int(env_admin_id)
        except ValueError:
            pass

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
        WHERE status = 'active'
    """)

    active_subscriptions = cursor.fetchone()[0]

    conn.close()

    message = (
        "👨‍💻 لوحة تحكم الـAdmin\n\n"
        f"👤 إجمالي العملاء: {total_users}\n"
        f"🔔 الطلبات المعلقة: {pending_requests}\n"
        f"✅ الاشتراكات الفعالة: {active_subscriptions}\n\n"
        "استخدم الأوامر:\n"
        "/requests — الطلبات المعلقة\n"
        "/subscriptions — الاشتراكات\n"
        "/admin — الإحصائيات"
    )

    await update.message.reply_text(message)


# =========================================================
# /requests
# =========================================================

async def requests_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ هذا الأمر خاص بالـAdmin."
        )
        return

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            telegram_id,
            request_type,
            plan,
            device,
            created_at
        FROM requests
        WHERE status = 'pending'
        ORDER BY id DESC
        LIMIT 20
    """)

    requests = cursor.fetchall()

    conn.close()

    if not requests:
        await update.message.reply_text(
            "📭 لا توجد طلبات معلقة حالياً."
        )
        return

    for request in requests:

        request_id = request[0]
        telegram_id = request[1]
        request_type = request[2]
        plan = request[3]
        device = request[4]
        created_at = request[5]

        if request_type == "trial":

            title = "🎁 طلب تجربة مجانية"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ تفعيل 24 ساعة",
                        callback_data=f"approve_trial_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ رفض",
                        callback_data=f"reject_{request_id}"
                    )
                ]
            ]

        else:

            title = "💰 طلب اشتراك"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "365 يوم",
                        callback_data=f"activate_365_{request_id}"
                    ),
                    InlineKeyboardButton(
                        "30 يوم",
                        callback_data=f"activate_30_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "90 يوم",
                        callback_data=f"activate_90_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ رفض",
                        callback_data=f"reject_{request_id}"
                    )
                ]
            ]

        text = (
            f"{title}\n\n"
            f"🆔 الطلب: #{request_id}\n"
            f"👤 Telegram ID: {telegram_id}\n"
            f"📦 الباقة: {plan if plan else '—'}\n"
            f"📺 الجهاز: {device if device else '—'}\n"
            f"🕐 التاريخ: {created_at}"
        )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# =========================================================
# /subscriptions
# =========================================================

async def subscriptions_command(
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
        SELECT
            telegram_id,
            plan,
            start_date,
            end_date,
            status
        FROM subscriptions
        ORDER BY id DESC
        LIMIT 30
    """)

    subscriptions = cursor.fetchall()

    conn.close()

    if not subscriptions:
        await update.message.reply_text(
            "📭 لا توجد اشتراكات حتى الآن."
        )
        return

    message = "📋 الاشتراكات:\n\n"

    for sub in subscriptions:

        telegram_id = sub[0]
        plan = sub[1]
        start_date = sub[2]
        end_date = sub[3]
        status = sub[4]

        status_text = (
            "🟢 فعال"
            if status == "active"
            else "🔴 منتهي"
        )

        message += (
            f"{status_text}\n"
            f"🆔 {telegram_id}\n"
            f"📦 {plan}\n"
            f"▶️ {start_date}\n"
            f"⏹️ {end_date}\n\n"
        )

    await update.message.reply_text(message)


# =========================================================
# أزرار المستخدم + الـAdmin
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    user = query.from_user

    # =====================================================
    # تجربة مجانية
    # =====================================================

    if query.data == "trial":

        keyboard = [
            [
                InlineKeyboardButton(
                    "📱 Android TV",
                    callback_data="device_android"
                )
            ],
            [
                InlineKeyboardButton(
                    "📺 LG Smart TV",
                    callback_data="device_lg"
                )
            ],
            [
                InlineKeyboardButton(
                    "📺 Samsung Smart TV",
                    callback_data="device_samsung"
                )
            ],
        ]

        await query.message.reply_text(
            "🎁 تجربة مجانية لمدة 24 ساعة\n\n"
            "اختر نوع الجهاز:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # =====================================================
    # الباقات
    # =====================================================

    if query.data == "plans":

        keyboard = [
            [
                InlineKeyboardButton(
                    "✨ VIP — 60€",
                    callback_data="plan_vip"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚜️ ذهبي — 30€",
                    callback_data="plan_gold"
                )
            ],
            [
                InlineKeyboardButton(
                    "💎 ماسي — 45€",
                    callback_data="plan_diamond"
                )
            ],
            [
                InlineKeyboardButton(
                    "📞 التواصل مع الدعم",
                    url="https://t.me/sfort4k"
                )
            ],
        ]

        if not os.path.exists(PLANS_IMAGE):
            await query.message.reply_text(
                "⚠️ تعذر تحميل صورة الباقات حالياً."
            )
            return

        with open(PLANS_IMAGE, "rb") as photo:

            await query.message.reply_photo(
                photo=photo,
                caption=(
                    "💰 الباقات والأسعار\n\n"
                    "✨ VIP — 60€\n"
                    "⚜️ ذهبي — 30€\n"
                    "💎 ماسي — 45€\n\n"
                    "💳 الدفع عن طريق PayPal أو Stripe.\n\n"
                    "📞 الدعم: @sfort4k"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        return

    # =====================================================
    # اختيار الجهاز
    # =====================================================

    if query.data.startswith("device_"):

        devices = {
            "device_android": "📱 Android TV",
            "device_lg": "📺 LG Smart TV",
            "device_samsung": "📺 Samsung Smart TV",
        }

        device_name = devices.get(
            query.data,
            "غير معروف"
        )

        save_user(user)

        request_id = create_request(
            telegram_id=user.id,
            request_type="trial",
            device=device_name
        )

        admin_id = get_admin_id()

        username = (
            f"@{user.username}"
            if user.username
            else "بدون Username"
        )

        if admin_id is not None:

            notification = (
                "🔔 طلب تجربة مجانية جديد\n\n"
                f"🆔 الطلب: #{request_id}\n"
                f"👤 الاسم: {user.full_name}\n"
                f"📱 Username: {username}\n"
                f"🆔 Telegram ID: {user.id}\n"
                f"📺 الجهاز: {device_name}\n\n"
                "اختر الإجراء:"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ تفعيل 24 ساعة",
                        callback_data=f"approve_trial_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ رفض",
                        callback_data=f"reject_{request_id}"
                    )
                ]
            ]

            await context.bot.send_message(
                chat_id=admin_id,
                text=notification,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        await query.message.reply_text(
            "✅ تم تسجيل طلب التجربة بنجاح.\n\n"
            f"📺 الجهاز: {device_name}\n"
            "⏰ المدة: 24 ساعة\n\n"
            "👨‍💻 سيتم مراجعة طلبك من الإدارة."
        )

        return

        # =====================================================
    # استقبال صورة MAC Address + Device Code
    # =====================================================

    if update.message and update.message.photo:

        device_name = context.user_data.get("trial_device")

        if not device_name:
            await update.message.reply_text(
                "❌ لم يتم اختيار نوع الجهاز.\n\n"
                "يرجى الضغط على تجربة مجانية واختيار جهازك أولاً."
            )
            return

        save_user(user)

        photo = update.message.photo[-1]

        request_id = create_request(
            telegram_id=user.id,
            request_type="trial",
            device=device_name
        )

        admin_id = get_admin_id()

        username = (
            f"@{user.username}"
            if user.username
            else "بدون Username"
        )

        if admin_id is not None:

            notification = (
                "🔔 طلب تجربة مجانية جديد\n\n"
                f"🆔 الطلب: #{request_id}\n"
                f"👤 الاسم: {user.full_name}\n"
                f"📱 Username: {username}\n"
                f"🆔 Telegram ID: {user.id}\n"
                f"📺 الجهاز: {device_name}\n\n"
                "📸 المستخدم أرسل صورة تحتوي على بيانات الجهاز.\n"
                "راجع الصورة وتأكد من MAC Address وDevice Code.\n\n"
                "اختر الإجراء:"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ تفعيل 24 ساعة",
                        callback_data=f"approve_trial_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ رفض",
                        callback_data=f"reject_{request_id}"
                    )
                ]
            ]

            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=notification,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        await query.message.reply_text(
            "✅ تم استلام الصورة بنجاح.\n\n"
            f"📺 الجهاز: {device_name}\n"
            "⏰ التجربة: 24 ساعة\n\n"
            "👨‍💻 سيتم مراجعة بيانات الجهاز من الإدارة "
            "والتواصل معك بعد إكمال المراجعة."
        )

        # حذف بيانات الجهاز المؤقتة
        context.user_data.pop("trial_device", None)

        return
        
    # =====================================================
    # اختيار الباقة
    # =====================================================

    if query.data.startswith("plan_"):

        plans = {
            "plan_vip": "✨ VIP — 60€",
            "plan_gold": "⚜️ ذهبي — 30€",
            "plan_diamond": "💎 ماسي — 45€",
        }

        plan_name = plans.get(
            query.data,
            "باقة غير معروفة"
        )

        # نخزن الباقة مؤقتاً للمستخدم
        context.user_data["selected_plan"] = plan_name

        keyboard = [
            [
                InlineKeyboardButton(
                    "📅 30 يوم",
                    callback_data="duration_30"
                )
            ],
            [
                InlineKeyboardButton(
                    "📅 90 يوم",
                    callback_data="duration_90"
                )
            ],
            [
                InlineKeyboardButton(
                    "📅 سنة واحدة",
                    callback_data="duration_365"
                )
            ],
        ]

        await query.message.reply_text(
            f"📦 الباقة المختارة:\n\n"
            f"{plan_name}\n\n"
            "⏰ الآن اختر مدة الاشتراك:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # =====================================================
    # اختيار مدة الاشتراك
    # =====================================================

    if query.data.startswith("duration_"):

        durations = {
            "duration_30": ("30 يوم", 30),
            "duration_90": ("90 يوم", 90),
            "duration_365": ("سنة واحدة", 365),
        }

        duration_info = durations.get(query.data)

        if not duration_info:

            await query.message.reply_text(
                "❌ مدة غير معروفة."
            )

            return

        duration_text, days = duration_info

        plan_name = context.user_data.get("selected_plan")

        if not plan_name:

            await query.message.reply_text(
                "❌ لم يتم تحديد الباقة.\n\n"
                "يرجى العودة واختيار الباقة من جديد."
            )

            return

        save_user(user)

        # إنشاء الطلب بعد اختيار الباقة والمدة
        request_id = create_request(
            telegram_id=user.id,
            request_type="subscription",
            plan=f"{plan_name} — {duration_text}"
        )

        admin_id = get_admin_id()

        username = (
            f"@{user.username}"
            if user.username
            else "بدون Username"
        )

        if admin_id is not None:

            notification = (
                "💰 طلب اشتراك جديد\n\n"
                f"🆔 الطلب: #{request_id}\n"
                f"👤 الاسم: {user.full_name}\n"
                f"📱 Username: {username}\n"
                f"🆔 Telegram ID: {user.id}\n"
                f"📦 الباقة: {plan_name}\n"
                f"⏰ المدة المطلوبة: {duration_text}\n\n"
                "اختر الإجراء:"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ تفعيل 30 يوم",
                        callback_data=f"activate_30_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ تفعيل 90 يوم",
                        callback_data=f"activate_90_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ تفعيل سنة",
                        callback_data=f"activate_365_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ رفض",
                        callback_data=f"reject_{request_id}"
                    )
                ]
            ]

            await context.bot.send_message(
                chat_id=admin_id,
                text=notification,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        await query.message.reply_text(
            "✅ تم تسجيل طلب الاشتراك بنجاح.\n\n"
            f"📦 الباقة: {plan_name}\n"
            f"⏰ المدة: {duration_text}\n\n"
            "👨‍💻 سيتم مراجعة طلبك من الإدارة "
            "والتواصل معك لإكمال الإجراءات.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📞 التواصل مع الدعم",
                        url="https://t.me/sfort4k"
                    )
                ]
            ])
        )

        # حذف الاختيار المؤقت
        context.user_data.pop("selected_plan", None)

        return

    # =====================================================
    # حالة اشتراك المستخدم
    # =====================================================

    if query.data == "my_subscription":

        update_expired_subscriptions()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                plan,
                start_date,
                end_date,
                status
            FROM subscriptions
            WHERE telegram_id = ?
            AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """, (
            user.id,
        ))

        subscription = cursor.fetchone()

        conn.close()

        if not subscription:

            await query.message.reply_text(
                "📭 لا يوجد لديك اشتراك فعال حالياً."
            )

            return

        plan = subscription[0]
        start_date = subscription[1]
        end_date = subscription[2]

        await query.message.reply_text(
            "📋 اشتراكك الحالي\n\n"
            f"📦 الباقة: {plan}\n"
            f"▶️ البداية: {start_date}\n"
            f"⏹️ الانتهاء: {end_date}\n"
            "🟢 الحالة: فعال"
        )

        return

    # =====================================================
    # تفعيل تجربة
    # =====================================================

    if query.data.startswith("approve_trial_"):

        if not is_admin(user.id):
            await query.answer(
                "❌ غير مسموح.",
                show_alert=True
            )
            return

        request_id = int(
            query.data.replace(
                "approve_trial_",
                ""
            )
        )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT telegram_id
            FROM requests
            WHERE id = ?
        """, (
            request_id,
        ))

        result = cursor.fetchone()

        conn.close()

        if not result:

            await query.edit_message_text(
                "❌ الطلب غير موجود."
            )

            return

        customer_id = result[0]

        activate_subscription(
            telegram_id=customer_id,
            plan="🎁 تجربة مجانية",
            days=1
        )

        update_request_status(
            request_id,
            "approved"
        )

        await query.edit_message_text(
            "✅ تم تفعيل التجربة.\n\n"
            f"🆔 الطلب: #{request_id}\n"
            f"👤 العميل: {customer_id}\n"
            "⏰ المدة: 24 ساعة"
        )

        try:

            await context.bot.send_message(
                chat_id=customer_id,
                text=(
                    "🎉 تم قبول طلب التجربة المجانية!\n\n"
                    "⏰ مدة التجربة: 24 ساعة\n\n"
                    "✅ تم تسجيل الاشتراك بنجاح."
                )
            )

        except Exception:
            pass

        return

    # =====================================================
    # تفعيل اشتراك 365 / 30 / 90 يوم
    # =====================================================

    if query.data.startswith("activate_"):

        if not is_admin(user.id):
            await query.answer(
                "❌ غير مسموح.",
                show_alert=True
            )
            return

        parts = query.data.split("_")

        days = int(parts[1])
        request_id = int(parts[2])

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT telegram_id, plan
            FROM requests
            WHERE id = ?
        """, (
            request_id,
        ))

        result = cursor.fetchone()

        conn.close()

        if not result:

            await query.edit_message_text(
                "❌ الطلب غير موجود."
            )

            return

        customer_id = result[0]
        plan = result[1]

        start_date, end_date = activate_subscription(
            telegram_id=customer_id,
            plan=plan,
            days=days
        )

        update_request_status(
            request_id,
            "approved"
        )

        await query.edit_message_text(
            "✅ تم تفعيل الاشتراك بنجاح.\n\n"
            f"🆔 الطلب: #{request_id}\n"
            f"👤 العميل: {customer_id}\n"
            f"📦 الباقة: {plan}\n"
            f"⏰ المدة: {days} يوم\n"
            f"▶️ البداية: {start_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"⏹️ النهاية: {end_date.strftime('%Y-%m-%d %H:%M')}"
        )

        try:

            await context.bot.send_message(
                chat_id=customer_id,
                text=(
                    "🎉 تم تفعيل اشتراكك بنجاح!\n\n"
                    f"📦 الباقة: {plan}\n"
                    f"⏰ المدة: {days} يوم\n"
                    f"▶️ البداية: {start_date.strftime('%Y-%m-%d %H:%M')}\n"
                    f"⏹️ الانتهاء: {end_date.strftime('%Y-%m-%d %H:%M')}\n\n"
                    "✅ حالة الاشتراك: فعال"
                )
            )

        except Exception:
            pass

        return

    # =====================================================
    # رفض الطلب
    # =====================================================

    if query.data.startswith("reject_"):

        if not is_admin(user.id):
            await query.answer(
                "❌ غير مسموح.",
                show_alert=True
            )
            return

        request_id = int(
            query.data.replace(
                "reject_",
                ""
            )
        )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT telegram_id
            FROM requests
            WHERE id = ?
        """, (
            request_id,
        ))

        result = cursor.fetchone()

        conn.close()

        if not result:

            await query.edit_message_text(
                "❌ الطلب غير موجود."
            )

            return

        customer_id = result[0]

        update_request_status(
            request_id,
            "rejected"
        )

        await query.edit_message_text(
            "❌ تم رفض الطلب.\n\n"
            f"🆔 الطلب: #{request_id}"
        )

        try:

            await context.bot.send_message(
                chat_id=customer_id,
                text=(
                    "❌ نعتذر، تم رفض الطلب حالياً.\n\n"
                    "📞 للاستفسار تواصل مع الدعم."
                )
            )

        except Exception:
            pass

        return


# =========================================================
# تشغيل البوت
# =========================================================

init_database()

if not TOKEN:
    raise RuntimeError(
        "❌ BOT_TOKEN غير موجود في Environment Variables."
    )

app = Application.builder().token(TOKEN).build()


# =========================================================
# الأوامر
# =========================================================

app.add_handler(
    CommandHandler("start", start)
)

app.add_handler(
    CommandHandler("setadmin", set_admin)
)

app.add_handler(
    CommandHandler("myid", myid)
)

app.add_handler(
    CommandHandler("admin", admin_panel)
)

app.add_handler(
    CommandHandler("requests", requests_command)
)

app.add_handler(
    CommandHandler("subscriptions", subscriptions_command)
)


# =========================================================
# Callback Buttons
# =========================================================

app.add_handler(
    CallbackQueryHandler(button_handler)
)


# =========================================================
# Webhook / Render
# =========================================================

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

print("البوت v2 يعمل بنظام Webhook...")

app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    webhook_url=WEBHOOK_URL,
    allowed_updates=Update.ALL_TYPES,
)

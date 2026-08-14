import os
import threading
from flask import Flask

# --- ترفند بیدار نگه داشتن ربات در Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "ربات بیدار است و در حال کار! 🤖"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# اجرای وب سرور در یک Thread جداگانه
threading.Thread(target=run_web_server, daemon=True).start()
# ------------------------------------------

# بقیه کدهای ربات شما از اینجا شروع میشه...
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Telegram Bot - Refactored & Optimized (2026 Architecture)
Features:
- PicklePersistence (Robust & Async-safe DB)
- Modern FSM (Finite State Machine) for admin workflows
- Forced Join with "Check Membership" button (Huge UX improvement)
- Smart Media Handler (Supports all Telegram media types cleanly)
- Broadcast & Stats System
"""

import logging
import os
import uuid
import asyncio
from urllib.parse import urlparse
from typing import Dict, Any, Optional

import logging
import os
import uuid
import asyncio
from urllib.parse import urlparse
from typing import Dict, Any, Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, PicklePersistence
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, PicklePersistence
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

# ================= CONFIGURATION =================
# Best practice: Use environment variables. Fallback to hardcoded for easy testing.
# خواندن امن اطلاعات از محیط Render
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/Qwopall")

# اگر توکن در Render تنظیم نشده باشد، ربات ارور میده و متوجه میشی
if not TOKEN:
    raise ValueError("❌ توکن ربات در Environment Variables تنظیم نشده است!")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= PERSISTENCE =================
# Replaces manual JSON/TXT database. Thread-safe, async-safe, auto-saves everything.
persistence = PicklePersistence(filepath="bot_database.pickle")

# ================= HELPER FUNCTIONS =================
def is_valid_url(url: str) -> bool:
    if not url: return False
    if url.startswith("http://") or url.startswith("https://"):
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme) and bool(parsed.netloc)
        except ValueError: return False
    return url.startswith("tg://")

async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Membership check error: {e}")
        return False

def extract_media(message: Update.message) -> Optional[Dict[str, Any]]:
    """Extracts media type, file_id, and caption from any message."""
    if message.text:
        return {"type": "text", "caption": message.text}
    elif message.photo:
        return {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
    elif message.video:
        return {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
    elif message.animation:
        return {"type": "animation", "file_id": message.animation.file_id, "caption": message.caption or ""}
    elif message.document:
        return {"type": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
    elif message.sticker:
        return {"type": "sticker", "file_id": message.sticker.file_id, "caption": ""}
    elif message.audio:
        return {"type": "audio", "file_id": message.audio.file_id, "caption": message.caption or ""}
    elif message.voice:
        return {"type": "voice", "file_id": message.voice.file_id, "caption": message.caption or ""}
    return None

async def send_media(
    chat_id: int, msg_type: str, file_id: str, caption: str, 
    context: ContextTypes.DEFAULT_TYPE, reply_markup: InlineKeyboardMarkup = None,
    reply_to_message_id: int = None
):
    """Centralized, robust media sender with fallbacks."""
    try:
        kwargs = {
            "chat_id": chat_id,
            "reply_markup": reply_markup,
            "parse_mode": ParseMode.HTML
        }
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = reply_to_message_id
            kwargs["allow_sending_without_reply"] = True

        if msg_type == "text":
            return await context.bot.send_message(text=caption, **kwargs)
        elif msg_type == "photo":
            return await context.bot.send_photo(photo=file_id, caption=caption, **kwargs)
        elif msg_type == "video":
            return await context.bot.send_video(video=file_id, caption=caption, **kwargs)
        elif msg_type == "animation":
            return await context.bot.send_animation(animation=file_id, caption=caption, **kwargs)
        elif msg_type == "document":
            return await context.bot.send_document(document=file_id, caption=caption, **kwargs)
        elif msg_type == "sticker":
            return await context.bot.send_sticker(sticker=file_id, reply_markup=reply_markup, reply_to_message_id=reply_to_message_id)
        elif msg_type == "audio":
            return await context.bot.send_audio(audio=file_id, caption=caption, **kwargs)
        elif msg_type == "voice":
            return await context.bot.send_voice(voice=file_id, caption=caption, **kwargs)
    except (BadRequest, Forbidden) as e:
        logger.error(f"Send media error: {e}")
        # Fallback without parse mode or reply
        try:
            if msg_type == "text":
                return await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)
        except Exception: pass
    return None

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_data = context.bot_data
    
    # Register user for stats/broadcast
    if "users" not in bot_data: bot_data["users"] = {}
    bot_data["users"][user.id] = {"id": user.id, "name": user.full_name, "username": user.username}

    args = context.args
    if args and args[0].startswith("force_"):
        content_id = args[0]
        if "forced_contents" in bot_data and content_id in bot_data["forced_contents"]:
            if await is_member(user.id, context):
                content = bot_data["forced_contents"][content_id]
                await send_media(user.id, content['type'], content.get('file_id', ''), content.get('caption', ''), context)
                await context.bot.send_message(
                    ADMIN_ID,
                    f"✅ <b>کاربر محتوای جوین اجباری را دریافت کرد:</b>\n\n"
                    f"👤 نام: {user.full_name}\n"
                    f"🆔 آیدی: <code>{user.id}</code>",
                    parse_mode=ParseMode.HTML
                )
            else:
                # Save pending content for the "Check Membership" button
                context.user_data["pending_force_join"] = content_id
                keyboard = [
                    [InlineKeyboardButton("📢 عضویت در کانال", url=CHANNEL_LINK)],
                    [InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check_membership")]
                ]
                await update.message.reply_text(
                    "⚠️ <b>برای دریافت محتوا ابتدا باید در کانال عضو شوید:</b>\n\n"
                    "1️⃣ روی دکمه زیر بزنید و Start کنید.\n"
                    "2️⃣ سپس دکمه 'بررسی عضویت' را بزنید.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            return

    # Admin Menu
    if user.id == ADMIN_ID:
        keyboard = [
            [KeyboardButton("📢 ساخت پست شیشه‌ای"), KeyboardButton("🔗 جوین اجباری")],
            [KeyboardButton("📊 آمار ربات"), KeyboardButton("📢 پیام همگانی")],
            [KeyboardButton("❌ لغو عملیات")]
        ]
        await update.message.reply_text(
            f"سلام {user.first_name} عزیز! 👋\nبه پنل مدیریت پیشرفته خوش آمدید.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "سلام! پیام خود را ارسال کنید تا برای ادمین فرستاده شود. 📩",
            reply_markup=ReplyKeyboardRemove()
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Universal cancel command to clear FSM and user_data."""
    if update.effective_user.id != ADMIN_ID: return
    context.user_data.clear()
    await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=ReplyKeyboardRemove())
    await start(update, context)

# ================= ADMIN PANEL ROUTER =================
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_data = context.user_data

    if text == "❌ لغو عملیات":
        await cancel(update, context)
        return

    if text == "📊 آمار ربات":
        bot_data = context.bot_data
        total_users = len(bot_data.get("users", {}))
        total_forced = len(bot_data.get("forced_contents", {}))
        await update.message.reply_text(
            f"📊 <b>آمار ربات:</b>\n\n"
            f"👥 تعداد کل کاربران: <code>{total_users}</code>\n"
            f"🔗 لینک‌های جوین اجباری فعال: <code>{total_forced}</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if text == "📢 پیام همگانی":
        user_data["admin_mode"] = "broadcast"
        await update.message.reply_text("📢 پیام همگانی خود را ارسال کنید:")
        return

    if text == "🔗 جوین اجباری":
        user_data["admin_mode"] = "forced_content"
        await update.message.reply_text("🔗 محتوای جوین اجباری را ارسال کنید:")
        return

    if text == "📢 ساخت پست شیشه‌ای":
        user_data["admin_mode"] = "create_post"
        user_data["draft_post"] = {"buttons": []}
        await update.message.reply_text("📝 محتوای پست را ارسال کنید:")
        return

    # FSM Routing
    if user_data.get("admin_mode") == "broadcast":
        await handle_broadcast(update, context)
    elif user_data.get("admin_mode") == "forced_content":
        await handle_forced_content(update, context)
    elif user_data.get("admin_mode") == "create_post":
        await handle_post_creation(update, context)
    elif user_data.get("admin_mode") == "reply_mode":
        await handle_admin_reply(update, context)
    else:
        await update.message.reply_text("⚠️ لطفاً از دکمه‌های منو استفاده کنید.")

# ================= FEATURES LOGIC =================
async def handle_forced_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    bot_data = context.bot_data
    if "forced_contents" not in bot_data: bot_data["forced_contents"] = {}

    content_id = f"force_{uuid.uuid4().hex[:8]}"
    content_data = extract_media(message)
    
    if not content_data:
        await message.reply_text("❌ نوع پیام پشتیبانی نمی‌شود.")
        return

    bot_data["forced_contents"][content_id] = content_data
    bot_username = (await context.bot.get_me()).username
    deep_link = f"https://t.me/{bot_username}?start={content_id}"

    await message.reply_text(
        f"✅ <b>لینک جوین اجباری ساخته شد!</b>\n\n"
        f"🔗 <code>{deep_link}</code>\n\n"
        f"این لینک را در دکمه شیشه‌ای یا پیام‌های خود قرار دهید.",
        parse_mode=ParseMode.HTML
    )
    context.user_data.clear()
    await start(update, context)

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    bot_data = context.bot_data
    users = bot_data.get("users", {})
    
    if not users:
        await message.reply_text("❌ هیچ کاربری در ربات ثبت نشده است.")
        context.user_data.clear()
        return

    await message.reply_text(f"⏳ در حال ارسال پیام به {len(users)} کاربر...")
    content_data = extract_media(message)
    success, fail = 0, 0

    for uid in list(users.keys()):
        if uid == ADMIN_ID: continue
        res = await send_media(uid, content_data['type'], content_data.get('file_id', ''), content_data.get('caption', ''), context)
        if res: success += 1
        else: fail += 1
        await asyncio.sleep(0.05) # Anti-FloodWait Protection

    await message.reply_text(f"✅ <b>ارسال همگانی پایان یافت!</b>\n🟢 موفق: <code>{success}</code>\n🔴 ناموفق: <code>{fail}</code>", parse_mode=ParseMode.HTML)
    context.user_data.clear()
    await start(update, context)

async def handle_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user_data = context.user_data
    draft = user_data.get("draft_post", {})

    if 'type' not in draft:
        content_data = extract_media(message)
        if not content_data: return
        draft.update(content_data)
        user_data["draft_post"] = draft
        await show_post_preview(update, context)
        return

    if user_data.get("awaiting_btn") == "text":
        user_data["temp_btn"] = {"text": message.text}
        user_data["awaiting_btn"] = "url"
        await message.reply_text("🔗 لینک دکمه را ارسال کنید:")
        return

    if user_data.get("awaiting_btn") == "url":
        url = message.text.strip()
        if not is_valid_url(url):
            await message.reply_text("❌ لینک نامعتبر است!")
            return
        temp_btn = user_data.pop("temp_btn", {})
        temp_btn["url"] = url
        draft["buttons"].append([temp_btn])
        user_data["draft_post"] = draft
        user_data.pop("awaiting_btn", None)
        await message.reply_text("✅ دکمه اضافه شد.")
        await show_post_preview(update, context)

async def show_post_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    draft = user_data.get("draft_post", {})
    keyboard = [
        [InlineKeyboardButton("➕ افزودن دکمه شیشه‌ای", callback_data="add_btn")],
        [InlineKeyboardButton("✅ پیش‌نمایش کامل", callback_data="preview_full")],
        [InlineKeyboardButton("🚀 ارسال به کانال", callback_data="send_to_channel")]
    ]
    await update.message.reply_text("🛠 <b>تنظیمات پست:</b>\nتعداد دکمه‌ها: <code>{}</code>".format(len(draft.get('buttons', []))), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    await send_media(ADMIN_ID, draft['type'], draft.get('file_id', ''), draft.get('caption', ''), context)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    bot_data = context.bot_data
    
    # Anti-Block check
    if "blocked_users" in bot_data and user.id in bot_data["blocked_users"]:
        return

    content_data = extract_media(message)
    if not content_data: return

    if "user_messages" not in bot_data: bot_data["user_messages"] = {}
    bot_data["user_messages"][user.id] = {"message_id": message.message_id}

    is_mem = await is_member(user.id, context)
    status = "✅ عضو" if is_mem else "❌ عضو نیست"
    admin_caption = f"📩 <b>پیام جدید:</b>\n👤 {user.full_name} | <code>{user.id}</code>\n📢 وضعیت: {status}"

    keyboard = [
        [InlineKeyboardButton("📩 پاسخ (با نقل قول)", callback_data=f"reply_quote_{user.id}"),
         InlineKeyboardButton("✉️ پاسخ (مستقیم)", callback_data=f"reply_direct_{user.id}")],
        [InlineKeyboardButton("⛔️ بلاک کاربر", callback_data=f"block_{user.id}")]
    ]

    await send_media(ADMIN_ID, content_data['type'], content_data.get('file_id', ''), content_data.get('caption', ''), context)
    await context.bot.send_message(ADMIN_ID, admin_caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    await message.reply_text("✅ پیام شما ارسال شد. منتظر پاسخ باشید...")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user_data = context.user_data
    bot_data = context.bot_data
    
    target_uid = user_data.get("reply_target")
    mode = user_data.get("reply_mode")
    if not target_uid: return

    content_data = extract_media(message)
    if not content_data: return

    user_msg_info = bot_data.get("user_messages", {}).get(target_uid)
    reply_to_id = user_msg_info.get("message_id") if mode == "quote" else None

    sent = await send_media(target_uid, content_data['type'], content_data.get('file_id', ''), content_data.get('caption', ''), context, reply_to_message_id=reply_to_id)
    if sent: await message.reply_text(f"✅ پیام ارسال شد.", parse_mode=ParseMode.HTML)
    else: await message.reply_text("❌ خطا در ارسال.")
    user_data.clear()
    await start(update, context)

# ================= CALLBACK QUERIES =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_data = context.user_data
    bot_data = context.bot_data

    # === USER LOGIC ===
    if data == "check_membership":
        if await is_member(query.from_user.id, context):
            content_id = user_data.pop("pending_force_join", None)
            if content_id and "forced_contents" in bot_data and content_id in bot_data["forced_contents"]:
                content = bot_data["forced_contents"][content_id]
                await send_media(query.from_user.id, content['type'], content.get('file_id', ''), content.get('caption', ''), context)
                await query.edit_message_text("✅ عضویت شما تایید شد و محتوا ارسال گردید.")
            else:
                await query.edit_message_text("✅ عضویت شما تایید شد.")
        else:
            await query.answer("❌ هنوز عضو کانال نشده‌اید!", show_alert=True)
        return

    # === ADMIN LOGIC ===
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔️ فقط ادمین دسترسی دارد!")
        return

    if data.startswith("reply_"):
        parts = data.split("_")
        mode = parts[1] # quote or direct
        uid = int(parts[2])
        user_data["admin_mode"] = "reply_mode"
        user_data["reply_target"] = uid
        user_data["reply_mode"] = mode
        await query.message.reply_text(f"✉️ در حالت پاسخ <b>{'با نقل قول' if mode == 'quote' else 'مستقیم'}</b> هستید.\nپیام خود را ارسال کنید.", parse_mode=ParseMode.HTML)
        return

    if data.startswith("block_"):
        uid = int(data.split("_")[1])
        if "blocked_users" not in bot_data: bot_data["blocked_users"] = set()
        bot_data["blocked_users"].add(uid)
        await query.edit_message_text(f"⛔️ کاربر <code>{uid}</code> بلاک شد.", parse_mode=ParseMode.HTML)
        return

    if data == "add_btn":
        user_data["awaiting_btn"] = "text"
        await query.message.reply_text("📝 متن دکمه را ارسال کنید:")
        return

    if data == "preview_full":
        draft = user_data.get("draft_post", {})
        markup = InlineKeyboardMarkup(draft.get("buttons", [])) if draft.get("buttons") else None
        await send_media(ADMIN_ID, draft['type'], draft.get('file_id', ''), draft.get('caption', ''), context, reply_markup=markup)
        await query.answer("پیش‌نمایش ارسال شد.", show_alert=True)
        return

    if data == "send_to_channel":
        draft = user_data.get("draft_post", {})
        markup = InlineKeyboardMarkup(draft.get("buttons", [])) if draft.get("buttons") else None
        sent = await send_media(CHANNEL_ID, draft['type'], draft.get('file_id', ''), draft.get('caption', ''), context, reply_markup=markup)
        if sent:
            await query.edit_message_text("✅ پست با موفقیت به کانال ارسال شد!")
            user_data.clear()
            await start(update, context)
        else:
            await query.edit_message_text("❌ خطا در ارسال به کانال. ربات باید ادمین کانال باشد.")
        return

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception while handling an update: {context.error}")

# ================= MAIN EXECUTION =================
# ================= MAIN EXECUTION =================
def main() -> None:
    application = Application.builder().token(TOKEN).persistence(persistence).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Split Admin and User messages cleanly
    application.add_handler(MessageHandler(filters.User(ADMIN_ID) & ~filters.COMMAND, admin_panel_handler))
    application.add_handler(MessageHandler(~filters.User(ADMIN_ID) & ~filters.COMMAND, handle_user_message))

    application.add_error_handler(error_handler)

    print("🚀 ربات با معماری جدید و بهینه استارت شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

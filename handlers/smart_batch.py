import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

from config.settings import settings
from database.db import db
from utils.media_helper import (
    is_image_document, is_video_document, is_audio_document, is_pdf_document,
    get_file_extension, format_file_size, prepare_caption
)
from utils.telegram_checker import check_bot_channel_admin

logger = logging.getLogger(__name__)
batch_router = Router(name="batch_router")

# Active Batch Storage: {user_id: {"is_active": bool, "target_channel_id": int, "channel_title": str, "items": [...]}}
_active_batches: Dict[int, Dict[str, Any]] = {}

def is_batch_active(user_id: int) -> bool:
    """Checks if a user currently has an active batch collection session."""
    return user_id in _active_batches and _active_batches[user_id].get("is_active", False)

def get_user_batch(user_id: int) -> Optional[Dict[str, Any]]:
    return _active_batches.get(user_id)

def natural_sort_key(s: str) -> List[Any]:
    """Sort strings containing numbers naturally (e.g. File 2 before File 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s or '')]

def extract_media_metadata(message: Message) -> Dict[str, Any]:
    """Extracts essential metadata for sorting and batch processing."""
    file_name = "Untitled"
    file_size = 0
    media_type = "unknown"

    if message.photo:
        media_type = "photo"
        file_name = message.caption or f"Photo_{message.message_id}.jpg"
        file_size = message.photo[-1].file_size or 0
    elif message.video:
        media_type = "video"
        file_name = message.video.file_name or message.caption or f"Video_{message.message_id}.mp4"
        file_size = message.video.file_size or 0
    elif message.audio:
        media_type = "audio"
        file_name = message.audio.file_name or message.audio.title or f"Audio_{message.message_id}.mp3"
        file_size = message.audio.file_size or 0
    elif message.animation:
        media_type = "animation"
        file_name = message.animation.file_name or f"Animation_{message.message_id}.gif"
        file_size = message.animation.file_size or 0
    elif message.voice:
        media_type = "voice"
        file_name = f"Voice_{message.message_id}.ogg"
        file_size = message.voice.file_size or 0
    elif message.video_note:
        media_type = "video_note"
        file_name = f"VideoNote_{message.message_id}.mp4"
        file_size = message.video_note.file_size or 0
    elif message.document:
        doc = message.document
        file_name = doc.file_name or f"Document_{message.message_id}"
        file_size = doc.file_size or 0
        if is_pdf_document(doc):
            media_type = "pdf_document"
        elif is_image_document(doc):
            media_type = "photo_document"
        elif is_video_document(doc):
            media_type = "video_document"
        elif is_audio_document(doc):
            media_type = "audio_document"
        else:
            media_type = "document"
    elif message.text:
        media_type = "text"
        file_name = (message.text[:30] + "...") if len(message.text) > 30 else message.text
        file_size = len(message.text.encode("utf-8"))

    return {
        "id": message.message_id,
        "message": message,
        "media_type": media_type,
        "file_name": file_name,
        "file_size": file_size,
        "size_str": format_file_size(file_size),
        "date": message.date or datetime.now(),
        "caption": message.caption or message.text or ""
    }

def build_sorting_keyboard() -> InlineKeyboardMarkup:
    """Builds interactive sorting selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔤 Name: A ➔ Z", callback_data="sort_name_asc"),
            InlineKeyboardButton(text="🔤 Name: Z ➔ A", callback_data="sort_name_desc")
        ],
        [
            InlineKeyboardButton(text="⏱️ Oldest First (1➔N)", callback_data="sort_time_asc"),
            InlineKeyboardButton(text="⏱️ Newest First (N➔1)", callback_data="sort_time_desc")
        ],
        [
            InlineKeyboardButton(text="📦 Size: Small ➔ Large", callback_data="sort_size_asc"),
            InlineKeyboardButton(text="📦 Size: Large ➔ Small", callback_data="sort_size_desc")
        ],
        [
            InlineKeyboardButton(text="📑 Type: PDF ➔ Video ➔ Photo", callback_data="sort_type_asc"),
            InlineKeyboardButton(text="📑 Type: Photo ➔ Video ➔ PDF", callback_data="sort_type_desc")
        ],
        [
            InlineKeyboardButton(text="⚡ Original Order (As Sent)", callback_data="sort_original")
        ],
        [
            InlineKeyboardButton(text="📋 View Items List", callback_data="batch_view_list"),
            InlineKeyboardButton(text="❌ Discard Batch", callback_data="batch_discard")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Commands ---

@batch_router.message(Command("batch", "startbatch"))
async def cmd_start_batch(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if not await db.is_user_authenticated(user_id):
        await message.reply("🔒 <b>Access Denied!</b> Pehle /login karke Master Password enter karein.", parse_mode="HTML")
        return

    active_channel_id = await db.get_active_channel_id(user_id)
    if not active_channel_id:
        await message.reply(
            "⚠️ <b>Koi Target Channel select nahi hai!</b>\n\n"
            "Pehle /channels se apna destination channel select karein.",
            parse_mode="HTML"
        )
        return

    can_post, title, err = await check_bot_channel_admin(bot, active_channel_id)
    if not can_post:
        await message.reply(f"❌ <b>Channel Error:</b> {err or 'Bot admin nahi hai.'}", parse_mode="HTML")
        return

    # Start Batch Session
    _active_batches[user_id] = {
        "is_active": True,
        "started_at": datetime.now(),
        "target_channel_id": active_channel_id,
        "channel_title": title,
        "items": []
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏁 Finish & Sort Batch", callback_data="btn_finish_batch"),
            InlineKeyboardButton(text="❌ Cancel Batch", callback_data="batch_discard")
        ]
    ])

    text = (
        f"📦 <b>Smart Batch Collection Mode ACTIVE!</b>\n\n"
        f"🎯 <b>Target Channel:</b> {title}\n\n"
        f"<b>Kaise use karein?</b>\n"
        f"1. Ab aap jitna bhi media (PDFs, Videos, Photos, Audios, Docs) send ya forward karenge, bot unka metadata collect karta rahega (channel me abhi post nahi hoga).\n"
        f"2. Saari files send karne ke baad <b>/endbatch</b> command bhejein ya neeche diye gaye <b>Finish & Sort</b> button par tap karein.\n"
        f"3. Bot aapse Sorting Option (Name A-Z, Size, Time, Type) puchega aur exact usi order me channel me sequentially upload karega!\n\n"
        f"<i>Abhi apni files bhejna shuru karein (Total Collected: 0)...</i>"
    )
    await message.reply(text, reply_markup=kb, parse_mode="HTML")

@batch_router.message(Command("endbatch", "finishbatch"))
async def cmd_end_batch(message: Message):
    user_id = message.from_user.id
    if not is_batch_active(user_id):
        await message.reply("⚠️ Aapka koi active batch session nahi hai. Naya batch shuru karne ke liye /batch type karein.", parse_mode="HTML")
        return

    batch_data = _active_batches[user_id]
    items = batch_data["items"]
    count = len(items)

    if count == 0:
        await message.reply("⚠️ Batch me koi file collect nahi hui thi. Batch band kar diya gaya hai.", parse_mode="HTML")
        _active_batches.pop(user_id, None)
        return

    kb = build_sorting_keyboard()
    text = (
        f"🏁 <b>Batch Collection Complete!</b>\n\n"
        f"📊 <b>Total Collected Files:</b> <code>{count} items</code>\n"
        f"🎯 <b>Destination Channel:</b> {batch_data['channel_title']}\n\n"
        f"Aap in sabhi files ko channel me kis order/sequence me post karna chahte hain? "
        f"Neeche se apna preferred sorting order select karein:"
    )
    await message.reply(text, reply_markup=kb, parse_mode="HTML")

@batch_router.message(Command("cancelbatch"))
async def cmd_cancel_batch(message: Message):
    user_id = message.from_user.id
    if is_batch_active(user_id):
        _active_batches.pop(user_id, None)
        await message.reply("🗑️ <b>Batch Cancelled!</b> Collected media ko discard kar diya gaya hai.", parse_mode="HTML")
    else:
        await message.reply("Koi active batch session nahi hai.", parse_mode="HTML")

@batch_router.message(Command("batchstatus", "batchlist"))
async def cmd_batch_status(message: Message):
    user_id = message.from_user.id
    if not is_batch_active(user_id):
        await message.reply("Aapka koi active batch session nahi hai. Start karne ke liye /batch bhejein.", parse_mode="HTML")
        return

    batch = _active_batches[user_id]
    items = batch["items"]
    count = len(items)

    if count == 0:
        await message.reply("📦 <b>Batch Active:</b> Abhi tak 0 files collect hui hain.", parse_mode="HTML")
        return

    preview_lines = []
    for i, item in enumerate(items[:15], 1):
        clean_name = item["file_name"]
        if len(clean_name) > 30:
            clean_name = clean_name[:27] + "..."
        preview_lines.append(f"{i}. <code>{clean_name}</code> ({item['size_str']})")

    if count > 15:
        preview_lines.append(f"<i>...aur {count - 15} aur files</i>")

    list_text = "\n".join(preview_lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏁 Finish & Sort", callback_data="btn_finish_batch"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="batch_discard")
        ]
    ])

    await message.reply(
        f"📦 <b>Active Batch Status:</b>\n\n"
        f"📊 <b>Total Files:</b> {count}\n\n"
        f"{list_text}\n\n"
        f"Files add karte rahein ya <b>/endbatch</b> se sort karke publish karein.",
        reply_markup=kb,
        parse_mode="HTML"
    )

# --- Callbacks ---

@batch_router.callback_query(F.data == "btn_finish_batch")
async def on_btn_finish_batch(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_batch_active(user_id):
        await callback.answer("⚠️ Active batch nahi mila!", show_alert=True)
        return

    batch_data = _active_batches[user_id]
    items = batch_data["items"]
    count = len(items)

    if count == 0:
        await callback.message.edit_text("⚠️ Batch me koi file nahi thi. Batch band kar diya gaya hai.", parse_mode="HTML")
        _active_batches.pop(user_id, None)
        return

    kb = build_sorting_keyboard()
    text = (
        f"🏁 <b>Batch Collection Complete!</b>\n\n"
        f"📊 <b>Total Collected Files:</b> <code>{count} items</code>\n"
        f"🎯 <b>Destination Channel:</b> {batch_data['channel_title']}\n\n"
        f"Aap in sabhi files ko channel me kis order me post karna chahte hain? Select karein:"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@batch_router.callback_query(F.data == "batch_discard")
async def on_batch_discard(callback: CallbackQuery):
    user_id = callback.from_user.id
    _active_batches.pop(user_id, None)
    await callback.message.edit_text("🗑️ <b>Batch Discarded!</b> Koi bhi file channel me post nahi hui.", parse_mode="HTML")

@batch_router.callback_query(F.data == "batch_view_list")
async def on_batch_view_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_batch_active(user_id):
        await callback.answer("Batch expired!", show_alert=True)
        return

    batch = _active_batches[user_id]
    items = batch["items"]
    
    preview_lines = []
    for i, item in enumerate(items[:20], 1):
        clean_name = item["file_name"]
        if len(clean_name) > 28:
            clean_name = clean_name[:25] + "..."
        preview_lines.append(f"{i}. <code>{clean_name}</code> ({item['size_str']})")

    if len(items) > 20:
        preview_lines.append(f"<i>...aur {len(items) - 20} files</i>")

    list_text = "\n".join(preview_lines)
    kb = build_sorting_keyboard()

    await callback.message.edit_text(
        f"📋 <b>Collected Batch Items ({len(items)}):</b>\n\n"
        f"{list_text}\n\n"
        f"Ab apna sorting method select karein:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@batch_router.callback_query(F.data.startswith("sort_"))
async def on_sort_and_publish(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    sort_action = callback.data

    if not is_batch_active(user_id):
        await callback.answer("⚠️ Session expired!", show_alert=True)
        return

    batch_data = _active_batches.pop(user_id, None)
    if not batch_data or not batch_data.get("items"):
        await callback.answer("⚠️ No items to publish!", show_alert=True)
        return

    items: List[Dict[str, Any]] = batch_data["items"]
    target_channel_id = batch_data["target_channel_id"]
    channel_title = batch_data["channel_title"]
    
    # 1. Apply Sorting
    sort_label = "Original Order"
    if sort_action == "sort_name_asc":
        items.sort(key=lambda x: natural_sort_key(x["file_name"]))
        sort_label = "🔤 Name (A ➔ Z)"
    elif sort_action == "sort_name_desc":
        items.sort(key=lambda x: natural_sort_key(x["file_name"]), reverse=True)
        sort_label = "🔤 Name (Z ➔ A)"
    elif sort_action == "sort_time_asc":
        # Already in chronological arrival order
        sort_label = "⏱️ Time (Oldest First)"
    elif sort_action == "sort_time_desc":
        items.reverse()
        sort_label = "⏱️ Time (Newest First)"
    elif sort_action == "sort_size_asc":
        items.sort(key=lambda x: x["file_size"])
        sort_label = "📦 Size (Small ➔ Large)"
    elif sort_action == "sort_size_desc":
        items.sort(key=lambda x: x["file_size"], reverse=True)
        sort_label = "📦 Size (Large ➔ Small)"
    elif sort_action == "sort_type_asc":
        type_order = {"pdf_document": 1, "document": 2, "video": 3, "video_document": 3, "audio": 4, "audio_document": 4, "photo": 5, "photo_document": 5}
        items.sort(key=lambda x: (type_order.get(x["media_type"], 99), natural_sort_key(x["file_name"])))
        sort_label = "📑 Type (PDF ➔ Video ➔ Photo)"
    elif sort_action == "sort_type_desc":
        type_order = {"photo": 1, "photo_document": 1, "video": 2, "video_document": 2, "audio": 3, "audio_document": 3, "pdf_document": 4, "document": 5}
        items.sort(key=lambda x: (type_order.get(x["media_type"], 99), natural_sort_key(x["file_name"])))
        sort_label = "📑 Type (Photo ➔ Video ➔ PDF)"

    # 2. Inform User
    await callback.message.edit_text(
        f"🚀 <b>Dispatching Sorted Batch!</b>\n\n"
        f"📊 <b>Total Items:</b> {len(items)}\n"
        f"🔀 <b>Sorted by:</b> {sort_label}\n"
        f"🎯 <b>Channel:</b> {channel_title}\n\n"
        f"⏳ <i>Files are being queued and uploaded sequentially...</i>",
        parse_mode="HTML"
    )

    # 3. Push to upload queue in exact sorted order
    # Import upload_queue and active user tasks from media_uploader
    from handlers.media_uploader import upload_queue, _active_user_tasks
    user_settings = await db.get_user_settings(user_id)
    channel = await db.get_channel(target_channel_id)

    for idx, item in enumerate(items, 1):
        _active_user_tasks[user_id] = _active_user_tasks.get(user_id, 0) + 1
        
        status_msg = await callback.message.reply(
            f"📥 <i>Queued [{idx}/{len(items)}]: <b>{item['file_name'][:30]}</b></i>",
            parse_mode="HTML"
        )
        
        job = {
            "user_id": user_id,
            "target_channel_id": target_channel_id,
            "message": item["message"],
            "user_settings": user_settings,
            "channel": channel,
            "channel_title": channel_title,
            "channel_username": channel.username if channel else None,
            "status_msg": status_msg
        }
        await upload_queue.put(job)

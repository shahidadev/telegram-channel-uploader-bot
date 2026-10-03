import io
import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile, FSInputFile
)
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

from config.settings import settings
from database.db import db
from utils.media_helper import (
    is_image_document, is_video_document, is_audio_document, is_pdf_document,
    get_file_extension, format_file_size, prepare_caption
)
from thumbnail_engine import (
    generate_document_thumbnail, get_temp_file_path, cleanup_temp_files
)
from utils.telegram_checker import check_bot_channel_admin

logger = logging.getLogger(__name__)
uploader_router = Router(name="uploader_router")

# Global FIFO Upload Queue
upload_queue: asyncio.Queue = asyncio.Queue()
_worker_tasks: List[asyncio.Task] = []
_active_user_tasks: Dict[int, int] = {}  # {user_id: pending_jobs_count}

# Temporary cache for confirmation mode: {user_id: {"message": Message, ...}}
_pending_confirmations: Dict[int, Dict[str, Any]] = {}

MAX_BOT_DOWNLOAD_BYTES = settings.MAX_BOT_DOWNLOAD_MB * 1024 * 1024

def get_channel_post_url(channel_id: int, channel_username: Optional[str], message_id: int) -> str:
    """Generates direct telegram URL to a channel message."""
    if channel_username:
        return f"https://t.me/{channel_username}/{message_id}"
    
    clean_id = str(channel_id)
    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]
    elif clean_id.startswith("-"):
        clean_id = clean_id[1:]
    return f"https://t.me/c/{clean_id}/{message_id}"

def build_channel_button(channel: Any = None) -> Optional[InlineKeyboardMarkup]:
    """Generates clean channel join button and promo bot button.
    Supports MAIN_CHANNEL_USERNAME and PROMO_BOT_USERNAME from .env with dynamic fallbacks."""
    buttons = []

    # 1. Main Channel Join Button
    if settings.MAIN_CHANNEL_USERNAME:
        main_ch = settings.MAIN_CHANNEL_USERNAME.lstrip("@")
        buttons.append([
            InlineKeyboardButton(text=f"📢 Join @{main_ch}", url=f"https://t.me/{main_ch}")
        ])
    elif channel:
        if getattr(channel, "username", None):
            buttons.append([
                InlineKeyboardButton(text=f"📢 Join @{channel.username}", url=f"https://t.me/{channel.username}")
            ])
        elif getattr(channel, "invite_link", None):
            buttons.append([
                InlineKeyboardButton(text="📢 Join Channel", url=channel.invite_link)
            ])

    # 2. Promotional Bot Button
    if settings.PROMO_BOT_USERNAME:
        promo_bot = settings.PROMO_BOT_USERNAME.lstrip("@")
        buttons.append([
            InlineKeyboardButton(text=f"🤖 Bot: @{promo_bot}", url=f"https://t.me/{promo_bot}")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

# --- Robust Telegram Dispatch Helpers with Automatic HTML Fallback ---

async def safe_send_photo(
    bot: Bot,
    chat_id: int,
    photo: Any,
    caption: Optional[str] = None,
    reply_markup: Any = None,
    disable_notification: bool = False
) -> Message:
    """Sends photo with HTML parsing; gracefully falls back to plain text if HTML parsing fails."""
    try:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_notification=disable_notification
        )
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "can't parse entities" in err_msg or "entity" in err_msg:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        raise

async def safe_send_document(
    bot: Bot,
    chat_id: int,
    document: Any,
    caption: Optional[str] = None,
    thumbnail: Any = None,
    reply_markup: Any = None,
    disable_notification: bool = False
) -> Message:
    """Sends document with HTML parsing; gracefully falls back to plain text if HTML parsing fails."""
    try:
        return await bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            parse_mode="HTML",
            thumbnail=thumbnail,
            reply_markup=reply_markup,
            disable_notification=disable_notification
        )
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "can't parse entities" in err_msg or "entity" in err_msg:
            return await bot.send_document(
                chat_id=chat_id,
                document=document,
                caption=caption,
                parse_mode=None,
                thumbnail=thumbnail,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        raise

async def safe_send_video(
    bot: Bot,
    chat_id: int,
    video: Any,
    caption: Optional[str] = None,
    duration: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    reply_markup: Any = None,
    disable_notification: bool = False
) -> Message:
    """Sends video with HTML parsing; gracefully falls back to plain text if HTML parsing fails."""
    try:
        return await bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True,
            duration=duration,
            width=width,
            height=height,
            reply_markup=reply_markup,
            disable_notification=disable_notification
        )
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "can't parse entities" in err_msg or "entity" in err_msg:
            return await bot.send_video(
                chat_id=chat_id,
                video=video,
                caption=caption,
                parse_mode=None,
                supports_streaming=True,
                duration=duration,
                width=width,
                height=height,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        raise

async def safe_send_audio(
    bot: Bot,
    chat_id: int,
    audio: Any,
    caption: Optional[str] = None,
    title: Optional[str] = None,
    performer: Optional[str] = None,
    duration: Optional[int] = None,
    reply_markup: Any = None,
    disable_notification: bool = False
) -> Message:
    """Sends audio with HTML parsing; gracefully falls back to plain text if HTML parsing fails."""
    try:
        return await bot.send_audio(
            chat_id=chat_id,
            audio=audio,
            caption=caption,
            parse_mode="HTML",
            title=title,
            performer=performer,
            duration=duration,
            reply_markup=reply_markup,
            disable_notification=disable_notification
        )
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "can't parse entities" in err_msg or "entity" in err_msg:
            return await bot.send_audio(
                chat_id=chat_id,
                audio=audio,
                caption=caption,
                parse_mode=None,
                title=title,
                performer=performer,
                duration=duration,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        raise

async def safe_send_animation(
    bot: Bot,
    chat_id: int,
    animation: Any,
    caption: Optional[str] = None,
    reply_markup: Any = None,
    disable_notification: bool = False
) -> Message:
    try:
        return await bot.send_animation(
            chat_id=chat_id,
            animation=animation,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_notification=disable_notification
        )
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "can't parse entities" in err_msg or "entity" in err_msg:
            return await bot.send_animation(
                chat_id=chat_id,
                animation=animation,
                caption=caption,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        raise

async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Any = None,
    disable_notification: bool = False
) -> Message:
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_notification=disable_notification
        )
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "can't parse entities" in err_msg or "entity" in err_msg:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        raise

async def execute_channel_upload(
    bot: Bot,
    user_id: int,
    target_channel_id: int,
    message: Message,
    user_settings: Any,
    channel: Any
) -> Optional[Message]:
    """Executes the upload to the target channel in strict sequential order."""
    caption = prepare_caption(message, user_settings.custom_watermark)
    silent = user_settings.silent_mode
    preview_mode = user_settings.preview_mode
    channel_markup = build_channel_button(channel)
    
    sent_msg: Optional[Message] = None
    media_type = "unknown"

    # 1. Native Photo (Direct or Forwarded) - Always has native preview
    if message.photo:
        media_type = "photo"
        photo_id = message.photo[-1].file_id
        sent_msg = await safe_send_photo(
            bot=bot,
            chat_id=target_channel_id,
            photo=photo_id,
            caption=caption,
            reply_markup=channel_markup,
            disable_notification=silent
        )

    # 2. Native Playable Video (Direct or Forwarded) - Always has native preview & player
    elif message.video:
        media_type = "video"
        sent_msg = await safe_send_video(
            bot=bot,
            chat_id=target_channel_id,
            video=message.video.file_id,
            caption=caption,
            duration=message.video.duration,
            width=message.video.width,
            height=message.video.height,
            reply_markup=channel_markup,
            disable_notification=silent
        )

    # 3. Animation / GIF - Direct native animation
    elif message.animation:
        media_type = "animation"
        sent_msg = await safe_send_animation(
            bot=bot,
            chat_id=target_channel_id,
            animation=message.animation.file_id,
            caption=caption,
            reply_markup=channel_markup,
            disable_notification=silent
        )

    # 4. Audio / Music - Direct native audio player
    elif message.audio:
        media_type = "audio"
        sent_msg = await safe_send_audio(
            bot=bot,
            chat_id=target_channel_id,
            audio=message.audio.file_id,
            caption=caption,
            title=message.audio.title,
            performer=message.audio.performer,
            duration=message.audio.duration,
            reply_markup=channel_markup,
            disable_notification=silent
        )

    # 5. Voice Notes
    elif message.voice:
        media_type = "voice"
        try:
            sent_msg = await bot.send_voice(
                chat_id=target_channel_id,
                voice=message.voice.file_id,
                caption=caption,
                parse_mode="HTML",
                duration=message.voice.duration,
                disable_notification=silent
            )
        except TelegramBadRequest:
            sent_msg = await bot.send_voice(
                chat_id=target_channel_id,
                voice=message.voice.file_id,
                caption=caption,
                parse_mode=None,
                duration=message.voice.duration,
                disable_notification=silent
            )

    # 6. Video Note (Circle Video)
    elif message.video_note:
        media_type = "video_note"
        sent_msg = await bot.send_video_note(
            chat_id=target_channel_id,
            video_note=message.video_note.file_id,
            duration=message.video_note.duration,
            disable_notification=silent
        )

    # 7. Document (PDFs, eBooks, Office Docs, Generic Documents)
    elif message.document:
        doc = message.document
        file_size = doc.file_size or 0
        ext = get_file_extension(doc.file_name)

        if preview_mode:
            # A. Image sent as Document -> Convert to Native Photo
            if is_image_document(doc):
                media_type = "photo_converted"
                converted = False
                if file_size <= MAX_BOT_DOWNLOAD_BYTES:
                    temp_img = get_temp_file_path(ext or ".jpg")
                    try:
                        await bot.download(doc.file_id, destination=temp_img)
                        sent_msg = await safe_send_photo(
                            bot=bot,
                            chat_id=target_channel_id,
                            photo=FSInputFile(temp_img),
                            caption=caption,
                            reply_markup=channel_markup,
                            disable_notification=silent
                        )
                        converted = True
                    except Exception as e:
                        logger.warning(f"Could not convert image doc: {e}")
                    finally:
                        cleanup_temp_files(temp_img)

                if not converted:
                    sent_msg = await safe_send_document(
                        bot=bot,
                        chat_id=target_channel_id,
                        document=doc.file_id,
                        caption=caption,
                        reply_markup=channel_markup,
                        disable_notification=silent
                    )

            # B. Video sent as Document -> Convert to Playable Video
            elif is_video_document(doc):
                media_type = "video_converted"
                converted = False
                if file_size <= MAX_BOT_DOWNLOAD_BYTES:
                    temp_vid = get_temp_file_path(ext or ".mp4")
                    try:
                        await bot.download(doc.file_id, destination=temp_vid)
                        sent_msg = await safe_send_video(
                            bot=bot,
                            chat_id=target_channel_id,
                            video=FSInputFile(temp_vid),
                            caption=caption,
                            reply_markup=channel_markup,
                            disable_notification=silent
                        )
                        converted = True
                    except Exception as e:
                        logger.warning(f"Could not convert video doc: {e}")
                    finally:
                        cleanup_temp_files(temp_vid)

                if not converted:
                    sent_msg = await safe_send_document(
                        bot=bot,
                        chat_id=target_channel_id,
                        document=doc.file_id,
                        caption=caption,
                        reply_markup=channel_markup,
                        disable_notification=silent
                    )

            # C. Audio sent as Document -> Convert to Native Audio Player
            elif is_audio_document(doc):
                media_type = "audio_converted"
                converted = False
                if file_size <= MAX_BOT_DOWNLOAD_BYTES:
                    temp_aud = get_temp_file_path(ext or ".mp3")
                    try:
                        await bot.download(doc.file_id, destination=temp_aud)
                        sent_msg = await safe_send_audio(
                            bot=bot,
                            chat_id=target_channel_id,
                            audio=FSInputFile(temp_aud),
                            caption=caption,
                            reply_markup=channel_markup,
                            disable_notification=silent
                        )
                        converted = True
                    except Exception as e:
                        logger.warning(f"Could not convert audio doc: {e}")
                    finally:
                        cleanup_temp_files(temp_aud)

                if not converted:
                    sent_msg = await safe_send_document(
                        bot=bot,
                        chat_id=target_channel_id,
                        document=doc.file_id,
                        caption=caption,
                        reply_markup=channel_markup,
                        disable_notification=silent
                    )

            # D. PDF and All Other Documents -> Single Unified Post with Embedded 1st-Page Thumbnail
            else:
                media_type = "pdf_document" if is_pdf_document(doc) else "document"
                temp_doc_path = None
                temp_thumb_path = None

                if file_size <= MAX_BOT_DOWNLOAD_BYTES:
                    temp_doc_path = get_temp_file_path(ext or ".pdf")
                    temp_thumb_path = get_temp_file_path(".jpg")

                    try:
                        await bot.download(doc.file_id, destination=temp_doc_path)
                        thumb_created = generate_document_thumbnail(
                            input_file_path=temp_doc_path,
                            output_thumbnail_path=temp_thumb_path,
                            max_dim=320
                        )
                    except Exception as e:
                        logger.warning(f"Could not download or generate thumbnail for doc: {e}")
                        thumb_created = None

                    try:
                        thumb_input = FSInputFile(temp_thumb_path) if (thumb_created and os.path.exists(temp_thumb_path)) else None
                        doc_upload = FSInputFile(temp_doc_path, filename=doc.file_name or f"document{ext}")
                        
                        # Send everything together in ONE single unified post!
                        sent_msg = await safe_send_document(
                            bot=bot,
                            chat_id=target_channel_id,
                            document=doc_upload,
                            thumbnail=thumb_input,
                            caption=caption,
                            reply_markup=channel_markup,
                            disable_notification=silent
                        )
                    finally:
                        cleanup_temp_files(temp_doc_path, temp_thumb_path)

                else:
                    # File > 20MB: Send direct document file
                    sent_msg = await safe_send_document(
                        bot=bot,
                        chat_id=target_channel_id,
                        document=doc.file_id,
                        caption=caption,
                        reply_markup=channel_markup,
                        disable_notification=silent
                    )

        else:
            # Preview mode OFF: Send raw document directly
            media_type = "document"
            sent_msg = await safe_send_document(
                bot=bot,
                chat_id=target_channel_id,
                document=doc.file_id,
                caption=caption,
                reply_markup=channel_markup,
                disable_notification=silent
            )

    # 8. Plain / Formatted Text Message
    elif message.text:
        media_type = "text"
        sent_msg = await safe_send_message(
            bot=bot,
            chat_id=target_channel_id,
            text=caption or message.text,
            reply_markup=channel_markup,
            disable_notification=silent
        )

    if sent_msg:
        # Check auto-pin
        if user_settings.pin_post:
            try:
                await bot.pin_chat_message(
                    chat_id=target_channel_id,
                    message_id=sent_msg.message_id,
                    disable_notification=silent
                )
            except Exception as e:
                logger.debug(f"Auto-pin failed: {e}")

        # Log upload in DB
        await db.log_upload(user_id, target_channel_id, media_type, sent_msg.message_id)

    return sent_msg

# --- FIFO Background Worker System ---

async def queue_worker(worker_id: int, bot: Bot):
    """Background worker that continuously pulls jobs from FIFO upload_queue."""
    logger.info(f"Upload Queue Worker #{worker_id} started.")
    while True:
        try:
            job = await upload_queue.get()
        except asyncio.CancelledError:
            break

        user_id = job["user_id"]
        target_channel_id = job["target_channel_id"]
        message = job["message"]
        user_settings = job["user_settings"]
        channel = job["channel"]
        title = job["channel_title"]
        channel_username = job["channel_username"]
        status_msg = job.get("status_msg")

        try:
            # Re-verify admin permission before upload
            can_post, _, err = await check_bot_channel_admin(bot, target_channel_id)
            if not can_post:
                if status_msg:
                    await status_msg.edit_text(f"❌ <b>Target Channel Error:</b> {err}", parse_mode="HTML")
                upload_queue.task_done()
                _active_user_tasks[user_id] = max(0, _active_user_tasks.get(user_id, 1) - 1)
                continue

            # Execute with FloodWait auto-retry
            max_retries = 3
            sent_msg = None
            for attempt in range(max_retries):
                try:
                    sent_msg = await execute_channel_upload(
                        bot=bot,
                        user_id=user_id,
                        target_channel_id=target_channel_id,
                        message=message,
                        user_settings=user_settings,
                        channel=channel
                    )
                    break
                except TelegramRetryAfter as e:
                    logger.warning(f"Telegram FloodWait hit. Sleeping for {e.retry_after}s...")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    logger.error(f"Attempt {attempt+1} upload error: {e}")
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(1)

            # Update progress
            _active_user_tasks[user_id] = max(0, _active_user_tasks.get(user_id, 1) - 1)
            remaining = _active_user_tasks.get(user_id, 0)

            if sent_msg and status_msg:
                post_url = get_channel_post_url(target_channel_id, channel_username, sent_msg.message_id)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 View in Channel", url=post_url)],
                    [InlineKeyboardButton(text="🔄 Switch Channel", callback_data="back_to_channels")]
                ])
                
                queue_suffix = f"\n\n⏳ <i>({remaining} item remaining in queue...)</i>" if remaining > 0 else ""
                await status_msg.edit_text(
                    f"✅ <b>Successfully Uploaded to {title}!</b>\n\n"
                    f"🚀 <b>Post ID:</b> <code>#{sent_msg.message_id}</code>"
                    f"{queue_suffix}",
                    reply_markup=kb,
                    parse_mode="HTML"
                )

        except TelegramForbiddenError:
            if status_msg:
                await status_msg.edit_text(f"❌ <b>Error:</b> Bot was removed from {title}.", parse_mode="HTML")
            await db.deactivate_channel(target_channel_id)
        except TelegramBadRequest as e:
            if status_msg:
                await status_msg.edit_text(f"❌ <b>Telegram API Error:</b> {e.message}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Queue worker upload failed: {e}", exc_info=True)
            if status_msg:
                await status_msg.edit_text(f"❌ <b>Upload Failed:</b> {str(e)}", parse_mode="HTML")
        finally:
            upload_queue.task_done()
            await asyncio.sleep(0.3)  # Small cooldown to prevent Telegram flood limits

def start_queue_workers(bot: Bot, num_workers: int = 1):
    """Starts background queue workers."""
    global _worker_tasks
    for i in range(num_workers):
        task = asyncio.create_task(queue_worker(i + 1, bot))
        _worker_tasks.append(task)
    logger.info(f"Started {num_workers} upload queue worker(s).")

def stop_queue_workers():
    """Cancels background queue workers."""
    global _worker_tasks
    for task in _worker_tasks:
        task.cancel()
    _worker_tasks.clear()

# --- Incoming Messages Handler (Supports Direct & Forwarded Media) ---

@uploader_router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def handle_incoming_upload(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    # 1. Check Authentication
    if not await db.is_user_authenticated(user_id):
        await message.reply("🔒 <b>Access Denied!</b> Pehle /login karke Master Password enter karein.", parse_mode="HTML")
        return

    # Check if User is in Active Batch Collection Mode
    from handlers.smart_batch import is_batch_active, extract_media_metadata, _active_batches
    if is_batch_active(user_id):
        batch = _active_batches.get(user_id)
        if batch and batch.get("is_active"):
            meta = extract_media_metadata(message)
            batch["items"].append(meta)
            count = len(batch["items"])
            await message.reply(
                f"📦 <b>[Batch #{count}]</b> Added: <code>{meta['file_name'][:25]}</code> ({meta['size_str']})\n"
                f"<i>Send more files or use /endbatch to sort & upload.</i>",
                parse_mode="HTML"
            )
            return

    # 2. Check Target Channel
    active_channel_id = await db.get_active_channel_id(user_id)
    if not active_channel_id:
        await message.reply(
            "⚠️ <b>Koi Target Channel select nahi hai!</b>\n\n"
            "File post karne ke liye pehle /channels command se apna channel select karein.",
            parse_mode="HTML"
        )
        return

    # 3. Check Channel Status & Bot Admin Rights
    can_post, title, err = await check_bot_channel_admin(bot, active_channel_id)
    if not can_post:
        await message.reply(
            f"❌ <b>Target Channel Error:</b>\n{err or 'Bot channel me admin nahi hai.'}\n\n"
            f"Kripya /channels se naya channel select karein.",
            parse_mode="HTML"
        )
        await db.deactivate_channel(active_channel_id)
        return

    channel = await db.get_channel(active_channel_id)
    user_settings = await db.get_user_settings(user_id)

    # 4. Check Confirmation Mode
    if user_settings.confirm_mode:
        _pending_confirmations[user_id] = {
            "message": message,
            "target_channel_id": active_channel_id,
            "channel_title": title,
            "channel_username": channel.username if channel else None
        }
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Publish Now", callback_data="do_publish"),
                InlineKeyboardButton(text="❌ Discard", callback_data="do_discard")
            ]
        ])
        await message.reply(
            f"👀 <b>Review Mode:</b>\n\n"
            f"Aapki file <b>{title}</b> par post hone ke liye ready hai.\n"
            f"Kya aap ise abhi channel me publish karna chahte hain?",
            reply_markup=confirm_kb,
            parse_mode="HTML"
        )
        return

    # 5. Push into Sequential FIFO Queue
    _active_user_tasks[user_id] = _active_user_tasks.get(user_id, 0) + 1
    pending_count = _active_user_tasks[user_id]
    
    if pending_count == 1:
        progress_msg = await message.reply("⏳ <i>Processing & Uploading...</i>", parse_mode="HTML")
    else:
        progress_msg = await message.reply(f"📥 <i>Added to queue (Position #{pending_count})...</i>", parse_mode="HTML")

    job = {
        "user_id": user_id,
        "target_channel_id": active_channel_id,
        "message": message,
        "user_settings": user_settings,
        "channel": channel,
        "channel_title": title,
        "channel_username": channel.username if channel else None,
        "status_msg": progress_msg
    }
    
    await upload_queue.put(job)

@uploader_router.callback_query(F.data == "do_publish")
async def on_confirm_publish(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = _pending_confirmations.pop(user_id, None)
    
    if not data:
        await callback.answer("⚠️ Session expired ya message already processed!", show_alert=True)
        return

    msg = data["message"]
    target_id = data["target_channel_id"]
    title = data["channel_title"]
    username = data["channel_username"]
    user_settings = await db.get_user_settings(user_id)
    channel = await db.get_channel(target_id)

    status_msg = await callback.message.edit_text("⏳ <i>Queued for publishing...</i>", parse_mode="HTML")

    _active_user_tasks[user_id] = _active_user_tasks.get(user_id, 0) + 1
    job = {
        "user_id": user_id,
        "target_channel_id": target_id,
        "message": msg,
        "user_settings": user_settings,
        "channel": channel,
        "channel_title": title,
        "channel_username": username,
        "status_msg": status_msg
    }
    await upload_queue.put(job)

@uploader_router.callback_query(F.data == "do_discard")
async def on_discard_publish(callback: CallbackQuery):
    user_id = callback.from_user.id
    _pending_confirmations.pop(user_id, None)
    await callback.message.edit_text("🗑️ <b>Post Discarded!</b> Channel me kuch post nahi hua.", parse_mode="HTML")

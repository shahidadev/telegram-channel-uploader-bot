import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from utils.telegram_checker import check_bot_channel_admin

logger = logging.getLogger(__name__)
channel_router = Router(name="channel_router")

async def build_channels_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Builds inline keyboard listing all available channels with active channel marked."""
    channels = await db.get_active_channels()
    active_channel_id = await db.get_active_channel_id(user_id)
    
    keyboard = []
    for ch in channels:
        is_active = (ch.channel_id == active_channel_id)
        prefix = "✅ " if is_active else "📢 "
        suffix = " (Active)" if is_active else ""
        btn_text = f"{prefix}{ch.title}{suffix}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"select_ch:{ch.channel_id}")])
        
    action_row = [
        InlineKeyboardButton(text="🔄 Sync / Refresh", callback_data="refresh_channels"),
        InlineKeyboardButton(text="➕ Add Channel", callback_data="help_add_channel")
    ]
    keyboard.append(action_row)
    keyboard.append([InlineKeyboardButton(text="⚙️ Settings & Options", callback_data="open_settings")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@channel_router.message(Command("channels", "channel", "switch"))
async def cmd_channels(message: Message):
    user_id = message.from_user.id
    if not await db.is_user_authenticated(user_id):
        await message.answer("🔒 <b>Access Denied!</b> Pehle /login karke Master Password enter karein.", parse_mode="HTML")
        return

    channels = await db.get_active_channels()
    active_channel_id = await db.get_active_channel_id(user_id)
    active_ch = await db.get_channel(active_channel_id) if active_channel_id else None
    
    active_title = f"<b>{active_ch.title}</b>" if active_ch else "<i>None (Koi select nahi hai)</i>"
    
    markup = await build_channels_keyboard(user_id)
    
    text = (
        f"📺 <b>Channel Manager & Selector</b>\n\n"
        f"🎯 <b>Current Target:</b> {active_title}\n"
        f"📊 <b>Total Connected Channels:</b> <code>{len(channels)}</code>\n\n"
        f"Neeche se jis channel me upload karna ho uspar tap karke select karein:"
    )
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@channel_router.callback_query(F.data.startswith("select_ch:"))
async def on_select_channel(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not await db.is_user_authenticated(user_id):
        await callback.answer("🔒 Please login first via /login", show_alert=True)
        return

    channel_id = int(callback.data.split(":")[1])
    
    # Verify bot is still admin
    can_post, title, err = await check_bot_channel_admin(bot, channel_id)
    if not can_post:
        await callback.answer(f"⚠️ Error: {err or 'Permission revoked'}", show_alert=True)
        await db.deactivate_channel(channel_id)
        markup = await build_channels_keyboard(user_id)
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass
        return

    await db.set_active_channel(user_id, channel_id)
    await callback.answer(f"✅ Selected: {title}", show_alert=False)
    
    markup = await build_channels_keyboard(user_id)
    new_text = (
        f"🎯 <b>Target Channel Set:</b> <b>{title}</b>\n\n"
        f"✨ <b>Ab aap koi bhi media ya file bhej sakte hain:</b>\n"
        f"• 🖼️ <b>Photos</b>: Full preview photo me post hongi.\n"
        f"• 🎥 <b>Videos</b>: Streaming playable video player me post hongi.\n"
        f"• 📄 <b>PDFs</b>: Previewable PDF format me post hongi.\n"
        f"• 🎵 <b>Audio / Voice</b>: Native audio player me post hongi.\n\n"
        f"<i>Target badalne ke liye neeche se dusra channel select karein:</i>"
    )
    try:
        await callback.message.edit_text(new_text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass

@channel_router.callback_query(F.data == "refresh_channels")
async def on_refresh_channels(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    channels = await db.get_active_channels()
    
    active_count = 0
    for ch in channels:
        can_post, _, _ = await check_bot_channel_admin(bot, ch.channel_id)
        if not can_post:
            await db.deactivate_channel(ch.channel_id)
        else:
            active_count += 1

    await callback.answer(f"🔄 Channels synced! Active: {active_count}", show_alert=False)
    markup = await build_channels_keyboard(user_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        pass

@channel_router.callback_query(F.data == "help_add_channel")
async def on_help_add_channel(callback: CallbackQuery, bot: Bot):
    bot_info = await bot.get_me()
    text = (
        f"➕ <b>Channel me Bot kaise Add karein?</b>\n\n"
        f"1️⃣ Apne Telegram Channel ko open karein.\n"
        f"2️⃣ Channel Settings ➔ <b>Administrators</b> ➔ <b>Add Admin</b> par jayein.\n"
        f"3️⃣ Bot username search karein: <code>@{bot_info.username}</code>\n"
        f"4️⃣ Bot ko <b>'Post Messages'</b> permission dekar Save karein.\n\n"
        f"⚡ <i>Jaise hi aap Admin banayenge, bot automatically channel detect karke list me add kar lega!</i>\n\n"
        f"Aap manual add karne ke liye <code>/addchannel @username</code> ya Channel se koi post forward bhi kar sakte hain."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@channel_router.callback_query(F.data == "back_to_channels")
async def on_back_to_channels(callback: CallbackQuery):
    user_id = callback.from_user.id
    active_channel_id = await db.get_active_channel_id(user_id)
    active_ch = await db.get_channel(active_channel_id) if active_channel_id else None
    active_title = f"<b>{active_ch.title}</b>" if active_ch else "<i>None</i>"
    
    text = (
        f"📺 <b>Channel Manager & Selector</b>\n\n"
        f"🎯 <b>Current Target:</b> {active_title}\n\n"
        f"Upload karne ke liye apna channel select karein:"
    )
    markup = await build_channels_keyboard(user_id)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

@channel_router.message(Command("addchannel"))
async def cmd_add_channel(message: Message, bot: Bot):
    user_id = message.from_user.id
    if not await db.is_user_authenticated(user_id):
        await message.answer("🔒 Pehle /login karein.", parse_mode="HTML")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer(
            "ℹ️ <b>Usage:</b> <code>/addchannel @channel_username</code> ya <code>/addchannel -1001234567890</code>\n\n"
            "<i>(Ensure karein ki bot us channel me Admin added ho)</i>",
            parse_mode="HTML"
        )
        return

    target = parts[1].strip()
    try:
        chat = await bot.get_chat(target)
        can_post, title, err = await check_bot_channel_admin(bot, chat.id)
        if not can_post:
            await message.answer(f"❌ <b>Admin Check Failed:</b> {err}", parse_mode="HTML")
            return

        await db.add_or_update_channel(
            channel_id=chat.id,
            title=chat.title,
            username=chat.username,
            invite_link=chat.invite_link,
            can_post=True
        )
        await db.set_active_channel(user_id, chat.id)
        await message.answer(
            f"🎉 <b>Channel Successfully Added & Selected!</b>\n\n"
            f"📢 <b>Title:</b> {chat.title}\n"
            f"🆔 <b>ID:</b> <code>{chat.id}</code>\n\n"
            f"Ab jo bhi file aap bhejenge wo direct is channel par upload hogi.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ <b>Failed to add channel:</b> {str(e)}", parse_mode="HTML")


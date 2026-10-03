import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import db

logger = logging.getLogger(__name__)
settings_router = Router(name="settings_router")

class SettingsStates(StatesGroup):
    waiting_for_watermark = State()

async def build_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user_settings = await db.get_user_settings(user_id)
    
    prev_icon = "✅ ON (16:9 Page Screenshot)" if user_settings.preview_mode else "❌ OFF (Raw Docs)"
    silent_icon = "🔔 ON (Muted Post)" if user_settings.silent_mode else "🔕 OFF (Normal Sound)"
    pin_icon = "📌 ON (Auto-Pin)" if user_settings.pin_post else "❌ OFF"
    confirm_icon = "📝 Ask Confirm" if user_settings.confirm_mode else "⚡ Instant Post"
    wm_text = "✏️ Set/Edit" if not user_settings.custom_watermark else "🗑️ Clear Watermark"

    keyboard = [
        [InlineKeyboardButton(text=f"🖼️ Media Preview: {prev_icon}", callback_data="toggle_preview")],
        [InlineKeyboardButton(text=f"🔕 Silent Upload: {silent_icon}", callback_data="toggle_silent")],
        [InlineKeyboardButton(text=f"📌 Auto-Pin: {pin_icon}", callback_data="toggle_pin")],
        [InlineKeyboardButton(text=f"🛡️ Post Mode: {confirm_icon}", callback_data="toggle_confirm")],
        [InlineKeyboardButton(text=f"🏷️ Caption Watermark: {wm_text}", callback_data="manage_watermark")],
        [InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@settings_router.message(Command("settings"))
async def cmd_settings(message: Message):
    user_id = message.from_user.id
    if not await db.is_user_authenticated(user_id):
        await message.answer("🔒 Pehle /login karein.", parse_mode="HTML")
        return

    markup = await build_settings_keyboard(user_id)
    user_settings = await db.get_user_settings(user_id)
    
    wm_display = f"<code>{user_settings.custom_watermark}</code>" if user_settings.custom_watermark else "<i>None (No watermark)</i>"
    
    text = (
        f"⚙️ <b>Bot & Upload Preferences</b>\n\n"
        f"• <b>Media Preview Mode:</b> Renders clean 16:9 First-Page Screenshot above documents and auto-converts image/video files.\n"
        f"• <b>Silent Upload:</b> Posts to channel without pinging subscribers.\n"
        f"• <b>Post Mode:</b> Instant vs Review before publishing.\n"
        f"• <b>Current Watermark:</b> {wm_display}\n\n"
        f"Neeche diye gaye options par tap karke toggle karein:"
    )
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@settings_router.callback_query(F.data == "open_settings")
async def on_open_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await db.is_user_authenticated(user_id):
        await callback.answer("🔒 Please login first", show_alert=True)
        return

    markup = await build_settings_keyboard(user_id)
    user_settings = await db.get_user_settings(user_id)
    wm_display = f"<code>{user_settings.custom_watermark}</code>" if user_settings.custom_watermark else "<i>None</i>"
    
    text = (
        f"⚙️ <b>Bot & Upload Preferences</b>\n\n"
        f"• <b>Media Preview Mode:</b> Renders clean 16:9 First-Page Screenshot above documents.\n"
        f"• <b>Current Watermark:</b> {wm_display}\n\n"
        f"Change settings below:"
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

@settings_router.callback_query(F.data == "toggle_preview")
async def on_toggle_preview(callback: CallbackQuery):
    user_id = callback.from_user.id
    current = await db.get_user_settings(user_id)
    new_val = not current.preview_mode
    await db.update_user_setting(user_id, "preview_mode", int(new_val))
    await callback.answer(f"Media Preview: {'Enabled' if new_val else 'Disabled'}")
    markup = await build_settings_keyboard(user_id)
    await callback.message.edit_reply_markup(reply_markup=markup)

@settings_router.callback_query(F.data == "toggle_silent")
async def on_toggle_silent(callback: CallbackQuery):
    user_id = callback.from_user.id
    current = await db.get_user_settings(user_id)
    new_val = not current.silent_mode
    await db.update_user_setting(user_id, "silent_mode", int(new_val))
    await callback.answer(f"Silent Upload: {'Enabled' if new_val else 'Disabled'}")
    markup = await build_settings_keyboard(user_id)
    await callback.message.edit_reply_markup(reply_markup=markup)

@settings_router.callback_query(F.data == "toggle_pin")
async def on_toggle_pin(callback: CallbackQuery):
    user_id = callback.from_user.id
    current = await db.get_user_settings(user_id)
    new_val = not current.pin_post
    await db.update_user_setting(user_id, "pin_post", int(new_val))
    await callback.answer(f"Auto-Pin: {'Enabled' if new_val else 'Disabled'}")
    markup = await build_settings_keyboard(user_id)
    await callback.message.edit_reply_markup(reply_markup=markup)

@settings_router.callback_query(F.data == "toggle_confirm")
async def on_toggle_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    current = await db.get_user_settings(user_id)
    new_val = not current.confirm_mode
    await db.update_user_setting(user_id, "confirm_mode", int(new_val))
    await callback.answer(f"Post Mode: {'Review Before Post' if new_val else 'Instant Send'}")
    markup = await build_settings_keyboard(user_id)
    await callback.message.edit_reply_markup(reply_markup=markup)

@settings_router.callback_query(F.data == "manage_watermark")
async def on_manage_watermark(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    current = await db.get_user_settings(user_id)
    
    if current.custom_watermark:
        # If already exists, option to clear
        await db.update_user_setting(user_id, "custom_watermark", None)
        await callback.answer("🗑️ Watermark cleared!")
        markup = await build_settings_keyboard(user_id)
        await callback.message.edit_reply_markup(reply_markup=markup)
    else:
        # Prompt user to type new watermark
        await state.set_state(SettingsStates.waiting_for_watermark)
        await callback.message.answer(
            "✏️ <b>Custom Watermark / Caption Footer Set karein:</b>\n\n"
            "Aap jo bhi text yahan bhejenge (jaise <code>📢 Join @MyChannel | Powered by Bot</code>), "
            "wo automatically har upload hone wali file ke caption ke bottom me add ho jayega.\n\n"
            "<i>Abhi apna watermark text send karein (ya cancel karne ke liye /cancel type karein):</i>",
            parse_mode="HTML"
        )
        await callback.answer()

@settings_router.message(SettingsStates.waiting_for_watermark, F.text)
async def process_watermark_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Watermark update cancelled.", parse_mode="HTML")
        return

    new_wm = message.text.strip()
    await db.update_user_setting(user_id, "custom_watermark", new_wm)
    await state.clear()
    
    await message.answer(
        f"✅ <b>Watermark set ho gaya!</b>\n\n"
        f"Current footer:\n<blockquote>{new_wm}</blockquote>",
        parse_mode="HTML"
    )

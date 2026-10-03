import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from handlers.auth import AuthStates, is_rate_limited
from config.settings import settings

logger = logging.getLogger(__name__)
start_router = Router(name="start_router")

def build_dashboard_keyboard(is_auth: bool = True) -> InlineKeyboardMarkup:
    if not is_auth:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Login with Password", callback_data="trigger_login")]
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Select Target Channel", callback_data="back_to_channels")],
        [InlineKeyboardButton(text="📦 Start Smart Batch Upload", callback_data="start_batch_from_menu")],
        [
            InlineKeyboardButton(text="⚙️ Settings", callback_data="open_settings"),
            InlineKeyboardButton(text="📊 My Stats", callback_data="view_stats")
        ],
        [
            InlineKeyboardButton(text="📖 Help & Guide", callback_data="view_help"),
            InlineKeyboardButton(text="🔒 Logout", callback_data="trigger_logout")
        ]
    ])

@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    is_auth = await db.is_user_authenticated(user_id)

    if not is_auth:
        limited, remaining = is_rate_limited(user_id)
        if limited:
            await message.answer(f"⏳ <b>Too many attempts!</b> Please wait <code>{remaining}s</code>.", parse_mode="HTML")
            return

        await state.set_state(AuthStates.waiting_for_password)
        await message.answer(
            f"👋 <b>Namaste {message.from_user.first_name}!</b>\n\n"
            f"🤖 <b>Channel Media Uploader Bot</b> me aapka swagat hai.\n\n"
            f"🔒 <i>Ye bot password-protected hai. Kripya access unlock karne ke liye <b>Master Password</b> enter karein:</i>",
            parse_mode="HTML"
        )
        return

    # If Authenticated
    active_channel_id = await db.get_active_channel_id(user_id)
    active_ch = await db.get_channel(active_channel_id) if active_channel_id else None
    
    active_title = f"<b>{active_ch.title}</b>" if active_ch else "<i>None (Koi select nahi hai)</i>"
    channels = await db.get_active_channels()

    dashboard_text = (
        f"🤖 <b>Media Uploader Dashboard</b>\n\n"
        f"👤 <b>User:</b> {message.from_user.first_name} (<code>{user_id}</code>)\n"
        f"🎯 <b>Target Channel:</b> {active_title}\n"
        f"📺 <b>Connected Channels:</b> <code>{len(channels)}</code>\n\n"
        f"✨ <b>Media Engine Features:</b>\n"
        f"• <b>Direct / Forward Upload:</b> Send/Forward photos, videos, PDFs, audios directly.\n"
        f"• <b>Single Post Preview:</b> PDFs & docs get 1st-page screenshot thumbnail in a single post.\n"
        f"• <b>Smart Batch Upload & Sort:</b> Use <code>/batch</code> to collect files and sort by Name, Size, Time, or Type.\n"
        f"• <b>Strict FIFO Queue:</b> Memory-safe background workers prevent crashes and preserve order.\n\n"
        f"<i>Neeche diye gaye buttons se options manage karein:</i>"
    )
    await message.answer(dashboard_text, reply_markup=build_dashboard_keyboard(True), parse_mode="HTML")

@start_router.callback_query(F.data == "start_batch_from_menu")
async def on_start_batch_from_menu(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not await db.is_user_authenticated(user_id):
        await callback.answer("🔒 Pehle login karein!", show_alert=True)
        return

    active_channel_id = await db.get_active_channel_id(user_id)
    if not active_channel_id:
        await callback.answer("⚠️ Pehle /channels se target channel select karein!", show_alert=True)
        return

    from handlers.smart_batch import cmd_start_batch
    # Trigger batch start
    await cmd_start_batch(callback.message, bot)
    await callback.answer()

@start_router.callback_query(F.data == "trigger_login")
async def on_trigger_login(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    limited, remaining = is_rate_limited(user_id)
    if limited:
        await callback.answer(f"⏳ Wait {remaining}s cooldown", show_alert=True)
        return
    
    await state.set_state(AuthStates.waiting_for_password)
    await callback.message.answer("🔒 <b>Master Password enter karein:</b>", parse_mode="HTML")
    await callback.answer()

@start_router.callback_query(F.data == "trigger_logout")
async def on_trigger_logout(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await db.logout_user(user_id)
    await state.clear()
    await callback.answer("Logged out successfully!")
    await callback.message.edit_text(
        "👋 <b>Aap logout ho chuke hain.</b>\nDobara access karne ke liye /login karein.",
        reply_markup=build_dashboard_keyboard(False),
        parse_mode="HTML"
    )

@start_router.callback_query(F.data == "view_stats")
@start_router.message(Command("stats", "status"))
async def show_stats(event: Message | CallbackQuery):
    user_id = event.from_user.id
    if not await db.is_user_authenticated(user_id):
        if isinstance(event, Message):
            await event.answer("🔒 Pehle /login karein.", parse_mode="HTML")
        else:
            await event.answer("🔒 Please login first", show_alert=True)
        return

    stats = await db.get_stats(user_id)
    active_channel_id = await db.get_active_channel_id(user_id)
    active_ch = await db.get_channel(active_channel_id) if active_channel_id else None
    
    text = (
        f"📊 <b>Bot Statistics & Status</b>\n\n"
        f"🎯 <b>Active Target Channel:</b> {active_ch.title if active_ch else 'None'}\n"
        f"🚀 <b>Total Uploads by You:</b> <code>{stats['total_uploads']}</code>\n"
        f"📢 <b>Available Channels:</b> <code>{stats['total_channels']}</code>\n"
        f"👥 <b>Active Authenticated Users:</b> <code>{stats['auth_users']}</code>\n\n"
        f"🟢 <b>Status:</b> All systems operational."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data="back_to_dashboard")]
    ])
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()

@start_router.callback_query(F.data == "view_help")
@start_router.message(Command("help"))
async def show_help(event: Message | CallbackQuery):
    text = (
        f"📖 <b>Bot Usage Guide & Commands</b>\n\n"
        f"1️⃣ <b>Authentication:</b>\n"
        f"• <code>/login</code> : Enter Master Password to unlock access.\n"
        f"• <code>/logout</code> : Logout and lock session.\n\n"
        f"2️⃣ <b>Target Channel Management:</b>\n"
        f"• <code>/channels</code> : Select active channel to post uploads.\n"
        f"• Bot must be added as <b>Administrator</b> with 'Post Messages' permission.\n\n"
        f"3️⃣ <b>📦 Smart Batch Upload & Custom Sorting:</b>\n"
        f"• <code>/batch</code> : Start a batch session. Send/forward as many files as you want without immediate uploading.\n"
        f"• <code>/batchstatus</code> : View list of collected files in current batch.\n"
        f"• <code>/endbatch</code> : Finish collection and open the sorting menu:\n"
        f"   - 🔤 <b>Name (A ➔ Z / Z ➔ A)</b>: Natural alphanumeric sorting (Chapter 2 before Chapter 10).\n"
        f"   - ⏱️ <b>Time (Oldest First / Newest First)</b>: Arrival order sorting.\n"
        f"   - 📦 <b>Size (Small ➔ Large / Large ➔ Small)</b>: File size sorting.\n"
        f"   - 📑 <b>Type (PDF ➔ Video ➔ Photo / Reverse)</b>: Media format grouped sorting.\n"
        f"   - ⚡ <b>Original Order</b>: Upload exactly in received order.\n"
        f"• <code>/cancelbatch</code> : Discard collected batch.\n\n"
        f"4️⃣ <b>Visual Preview & Media Engine:</b>\n"
        f"• <b>PDFs / Documents:</b> 1st-page screenshot thumbnail embedded into a <b>single unified message</b>.\n"
        f"• <b>Photos:</b> Native visual photo post.\n"
        f"• <b>Videos:</b> Native playable video with streaming player.\n"
        f"• <b>Audios:</b> Native Telegram audio/music player.\n\n"
        f"5️⃣ <b>Settings & Buttons:</b>\n"
        f"• <code>/settings</code> : Watermark, Silent Posting, Auto-Pin, Confirmation Mode.\n"
        f"• Dynamic Join Channel button + Promotional Bot button on each post."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data="back_to_dashboard")]
    ])
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()

@start_router.callback_query(F.data == "back_to_dashboard")
async def on_back_to_dashboard(callback: CallbackQuery):
    user_id = callback.from_user.id
    active_channel_id = await db.get_active_channel_id(user_id)
    active_ch = await db.get_channel(active_channel_id) if active_channel_id else None
    active_title = f"<b>{active_ch.title}</b>" if active_ch else "<i>None</i>"
    channels = await db.get_active_channels()

    dashboard_text = (
        f"🤖 <b>Media Uploader Dashboard</b>\n\n"
        f"👤 <b>User:</b> {callback.from_user.first_name}\n"
        f"🎯 <b>Target Channel:</b> {active_title}\n"
        f"📺 <b>Connected Channels:</b> <code>{len(channels)}</code>\n\n"
        f"✨ Send any media to upload directly or use <code>/batch</code> for sorted uploads!"
    )
    await callback.message.edit_text(dashboard_text, reply_markup=build_dashboard_keyboard(True), parse_mode="HTML")

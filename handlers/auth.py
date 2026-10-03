import time
import logging
from typing import Dict, Tuple
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config.settings import settings
from database.db import db

logger = logging.getLogger(__name__)
auth_router = Router(name="auth_router")

# In-memory tracking for brute-force prevention: {user_id: (attempts_count, last_attempt_time)}
_failed_attempts: Dict[int, Tuple[int, float]] = {}

class AuthStates(StatesGroup):
    waiting_for_password = State()

def is_rate_limited(user_id: int) -> Tuple[bool, int]:
    """Check if user has exceeded max login attempts and is in cooldown."""
    if user_id not in _failed_attempts:
        return False, 0
    attempts, last_time = _failed_attempts[user_id]
    if attempts >= settings.MAX_LOGIN_ATTEMPTS:
        elapsed = time.time() - last_time
        if elapsed < settings.LOGIN_COOLDOWN_SECONDS:
            remaining = int(settings.LOGIN_COOLDOWN_SECONDS - elapsed)
            return True, remaining
        else:
            # Reset after cooldown expires
            _failed_attempts.pop(user_id, None)
            return False, 0
    return False, 0

def record_failed_attempt(user_id: int):
    attempts, _ = _failed_attempts.get(user_id, (0, 0))
    _failed_attempts[user_id] = (attempts + 1, time.time())

def clear_failed_attempts(user_id: int):
    _failed_attempts.pop(user_id, None)

@auth_router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await db.is_user_authenticated(user_id):
        await message.answer("✅ <b>Aap already authenticated hain!</b>\n\nChannels dekhne ke liye /channels use karein.", parse_mode="HTML")
        return

    limited, remaining = is_rate_limited(user_id)
    if limited:
        await message.answer(f"⏳ <b>Too many failed attempts!</b>\nPlease wait <code>{remaining}s</code> before trying again.", parse_mode="HTML")
        return

    await state.set_state(AuthStates.waiting_for_password)
    await message.answer(
        "🔒 <b>Authentication Required!</b>\n\n"
        "Kripya bot ka <b>Master Password</b> enter karein:\n"
        "<i>(Security ke liye aapka password message auto-delete ho jayega)</i>",
        parse_mode="HTML"
    )

@auth_router.message(AuthStates.waiting_for_password, F.text)
async def process_password(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    entered_password = message.text.strip()

    # Auto-delete user's password message for privacy & security
    if settings.AUTO_DELETE_PASSWORD:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except Exception:
            pass

    limited, remaining = is_rate_limited(user_id)
    if limited:
        await message.answer(f"⏳ <b>Too many attempts!</b> Please wait <code>{remaining}s</code>.", parse_mode="HTML")
        return

    if entered_password == settings.MASTER_PASSWORD:
        clear_failed_attempts(user_id)
        await db.authenticate_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
        await state.clear()
        
        # Get active channels to display next steps
        channels = await db.get_active_channels()
        
        kb_buttons = []
        if channels:
            for ch in channels:
                btn_text = f"📢 {ch.title}" + (f" (@{ch.username})" if ch.username else "")
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"select_ch:{ch.channel_id}")])
        
        kb_buttons.append([
            InlineKeyboardButton(text="🔄 Refresh Channels", callback_data="refresh_channels"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="open_settings")
        ])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

        ch_text = f"\n\n📢 <b>Available Channels ({len(channels)}):</b>\nNeeche se apna target channel select karein jisme files post karni hain:" if channels else "\n\n⚠️ <i>Abhi koi channel linked nahi hai. Bot ko apne channel me as an <b>Admin</b> add karein.</i>"

        await message.answer(
            f"🎉 <b>Authentication Successful!</b>\n"
            f"Welcome <b>{message.from_user.first_name}</b>, aapka bot access unlock ho chuka hai."
            f"{ch_text}",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        record_failed_attempt(user_id)
        attempts, _ = _failed_attempts.get(user_id, (1, 0))
        left = settings.MAX_LOGIN_ATTEMPTS - attempts
        
        if left > 0:
            await message.answer(f"❌ <b>Galat Password!</b>\nKripya dobara sahi password dalein (Attempts left: <code>{left}</code>):", parse_mode="HTML")
        else:
            await state.clear()
            await message.answer(f"🚫 <b>Max attempts exceeded!</b>\nBot <code>{settings.LOGIN_COOLDOWN_SECONDS}s</code> ke liye lock ho gaya hai.", parse_mode="HTML")

@auth_router.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await db.logout_user(user_id)
    await state.clear()
    await message.answer(
        "👋 <b>Aap successfully logout ho chuke hain!</b>\n\nDobara login karne ke liye /login ya /start karein.",
        parse_mode="HTML"
    )

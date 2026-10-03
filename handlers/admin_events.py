import logging
from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, ADMINISTRATOR, MEMBER, KICKED, LEFT

from database.db import db
from config.settings import settings

logger = logging.getLogger(__name__)
admin_events_router = Router(name="admin_events_router")

@admin_events_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=ADMINISTRATOR))
async def bot_added_as_admin(event: ChatMemberUpdated, bot: Bot):
    """Triggered when the bot is promoted to Admin in a channel or group."""
    chat = event.chat
    # Only process channels and supergroups
    if chat.type not in ("channel", "supergroup"):
        return

    new_member = event.new_chat_member
    can_post = getattr(new_member, "can_post_messages", True)

    await db.add_or_update_channel(
        channel_id=chat.id,
        title=chat.title or "Untitled Channel",
        username=chat.username,
        invite_link=chat.invite_link,
        can_post=can_post
    )
    logger.info(f"Bot added as admin to channel: {chat.title} ({chat.id}) - Can Post: {can_post}")

    # Optionally notify owner/admin if configured
    if settings.OWNER_ID:
        try:
            status_text = "✅ <b>Post Messages Permission: Granted</b>" if can_post else "⚠️ <b>Warning: Post Messages Permission missing!</b>"
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    f"📢 <b>Naya Channel Auto-Detected!</b>\n\n"
                    f"🏷️ <b>Title:</b> {chat.title}\n"
                    f"🆔 <b>ID:</b> <code>{chat.id}</code>\n"
                    f"🔗 <b>Username:</b> {f'@{chat.username}' if chat.username else 'Private'}\n"
                    f"{status_text}\n\n"
                    f"Ye channel ab /channels list me available hai."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.debug(f"Could not notify owner: {e}")

@admin_events_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED | LEFT | MEMBER))
async def bot_removed_or_demoted(event: ChatMemberUpdated, bot: Bot):
    """Triggered when the bot is removed, kicked, or demoted to regular member."""
    chat = event.chat
    if chat.type in ("channel", "supergroup"):
        await db.deactivate_channel(chat.id)
        logger.info(f"Bot was removed/demoted from channel: {chat.title} ({chat.id})")

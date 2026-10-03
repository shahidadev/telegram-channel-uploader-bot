import logging
from typing import Tuple, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)

async def check_bot_channel_admin(bot: Bot, channel_id: int) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Checks if the bot is an admin in the specified channel and can post messages.
    Returns: (can_post: bool, channel_title: Optional[str], error_message: Optional[str])
    """
    try:
        bot_info = await bot.get_me()
        chat = await bot.get_chat(channel_id)
        member = await bot.get_chat_member(channel_id, bot_info.id)
        
        status = member.status
        # In channels, admins can be creator or administrator with can_post_messages
        if status == "creator":
            return True, chat.title, None
        
        if status == "administrator":
            # Check can_post_messages attribute if present
            can_post = getattr(member, "can_post_messages", True)
            if can_post:
                return True, chat.title, None
            else:
                return False, chat.title, "Bot is an administrator, but lacks 'Post Messages' permission."
                
        return False, chat.title, f"Bot is not an administrator in {chat.title} (Status: {status})."

    except TelegramForbiddenError:
        return False, None, "Bot was blocked or removed from this channel."
    except TelegramBadRequest as e:
        return False, None, f"Channel not found or bot has not been added yet: {e.message}"
    except Exception as e:
        logger.error(f"Error checking channel admin rights for {channel_id}: {e}")
        return False, None, f"Unexpected error: {str(e)}"

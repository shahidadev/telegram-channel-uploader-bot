import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from config.settings import settings
from .models import User, Channel, UserSettings

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = settings.DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database schema if not exists."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    is_authenticated INTEGER DEFAULT 0,
                    active_channel_id INTEGER,
                    auth_date TEXT
                );
            """)

            # Channels table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    username TEXT,
                    invite_link TEXT,
                    can_post INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    added_at TEXT
                );
            """)

            # User Settings table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    silent_mode INTEGER DEFAULT 0,
                    preview_mode INTEGER DEFAULT 1,
                    pdf_mode TEXT DEFAULT 'banner',
                    pin_post INTEGER DEFAULT 0,
                    confirm_mode INTEGER DEFAULT 0,
                    custom_watermark TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
            """)

            # Migration: Ensure pdf_mode column exists in existing user_settings table
            try:
                await db.execute("ALTER TABLE user_settings ADD COLUMN pdf_mode TEXT DEFAULT 'banner';")
            except Exception:
                pass  # Already exists

            # Upload logs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS upload_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    media_type TEXT,
                    message_id INTEGER,
                    timestamp TEXT
                );
            """)
            await db.commit()
            logger.info("Database initialized successfully.")

    # --- User & Auth Methods ---

    async def get_user(self, user_id: int) -> Optional[User]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        user_id=row["user_id"],
                        username=row["username"],
                        first_name=row["first_name"],
                        is_authenticated=bool(row["is_authenticated"]),
                        active_channel_id=row["active_channel_id"],
                        auth_date=row["auth_date"]
                    )
        return None

    async def is_user_authenticated(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return user.is_authenticated if user else False

    async def authenticate_user(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, is_authenticated, auth_date)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    is_authenticated = 1,
                    auth_date = excluded.auth_date;
            """, (user_id, username, first_name, now))
            
            # Ensure default settings row exists
            await db.execute("""
                INSERT OR IGNORE INTO user_settings (user_id, preview_mode)
                VALUES (?, 1);
            """, (user_id,))
            
            await db.commit()
            return True

    async def logout_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET is_authenticated = 0 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def set_active_channel(self, user_id: int, channel_id: Optional[int]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET active_channel_id = ? WHERE user_id = ?", (channel_id, user_id))
            await db.commit()

    async def get_active_channel_id(self, user_id: int) -> Optional[int]:
        user = await self.get_user(user_id)
        return user.active_channel_id if user else None

    # --- Channel Management Methods ---

    async def add_or_update_channel(self, channel_id: int, title: str, username: Optional[str] = None,
                                    invite_link: Optional[str] = None, can_post: bool = True):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO channels (channel_id, title, username, invite_link, can_post, is_active, added_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    title = excluded.title,
                    username = excluded.username,
                    invite_link = excluded.invite_link,
                    can_post = excluded.can_post,
                    is_active = 1;
            """, (channel_id, title, username, invite_link, int(can_post), now))
            await db.commit()
            logger.info(f"Channel {title} ({channel_id}) registered/updated.")

    async def get_active_channels(self) -> List[Channel]:
        channels = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM channels WHERE is_active = 1 AND can_post = 1 ORDER BY added_at DESC") as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    channels.append(Channel(
                        channel_id=row["channel_id"],
                        title=row["title"],
                        username=row["username"],
                        invite_link=row["invite_link"],
                        can_post=bool(row["can_post"]),
                        is_active=bool(row["is_active"]),
                        added_at=row["added_at"]
                    ))
        return channels

    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM channels WHERE channel_id = ?", (channel_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Channel(
                        channel_id=row["channel_id"],
                        title=row["title"],
                        username=row["username"],
                        invite_link=row["invite_link"],
                        can_post=bool(row["can_post"]),
                        is_active=bool(row["is_active"]),
                        added_at=row["added_at"]
                    )
        return None

    async def deactivate_channel(self, channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE channels SET is_active = 0, can_post = 0 WHERE channel_id = ?", (channel_id,))
            # If any user had this as active channel, reset or let it be
            await db.commit()

    async def delete_channel(self, channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
            await db.execute("UPDATE users SET active_channel_id = NULL WHERE active_channel_id = ?", (channel_id,))
            await db.commit()

    # --- User Settings Methods ---

    async def get_user_settings(self, user_id: int) -> UserSettings:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    row_keys = row.keys()
                    pdf_mode_val = row["pdf_mode"] if "pdf_mode" in row_keys and row["pdf_mode"] else "banner"
                    return UserSettings(
                        user_id=row["user_id"],
                        silent_mode=bool(row["silent_mode"]),
                        preview_mode=bool(row["preview_mode"]),
                        pdf_mode=pdf_mode_val,
                        pin_post=bool(row["pin_post"]),
                        confirm_mode=bool(row["confirm_mode"]),
                        custom_watermark=row["custom_watermark"]
                    )
                else:
                    # Create default
                    await db.execute("INSERT OR IGNORE INTO user_settings (user_id, preview_mode, pdf_mode) VALUES (?, 1, 'banner')", (user_id,))
                    await db.commit()
                    return UserSettings(user_id=user_id, preview_mode=True, pdf_mode="banner")

    async def update_user_setting(self, user_id: int, field: str, value: Any):
        allowed_fields = {"silent_mode", "preview_mode", "pdf_mode", "pin_post", "confirm_mode", "custom_watermark"}
        if field not in allowed_fields:
            raise ValueError(f"Invalid setting field: {field}")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Ensure row exists
            await db.execute("INSERT OR IGNORE INTO user_settings (user_id, preview_mode, pdf_mode) VALUES (?, 1, 'banner')", (user_id,))
            await db.execute(f"UPDATE user_settings SET {field} = ? WHERE user_id = ?", (value, user_id))
            await db.commit()

    # --- Upload Logs & Stats ---

    async def log_upload(self, user_id: int, channel_id: int, media_type: str, message_id: int):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO upload_logs (user_id, channel_id, media_type, message_id, timestamp)
                VALUES (?, ?, ?, ?, ?);
            """, (user_id, channel_id, media_type, message_id, now))
            await db.commit()

    async def get_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            if user_id:
                async with db.execute("SELECT COUNT(*) FROM upload_logs WHERE user_id = ?", (user_id,)) as c1:
                    total_uploads = (await c1.fetchone())[0]
            else:
                async with db.execute("SELECT COUNT(*) FROM upload_logs") as c1:
                    total_uploads = (await c1.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM channels WHERE is_active = 1") as c2:
                total_channels = (await c2.fetchone())[0]

            async with db.execute("SELECT COUNT(*) FROM users WHERE is_authenticated = 1") as c3:
                auth_users = (await c3.fetchone())[0]

            return {
                "total_uploads": total_uploads,
                "total_channels": total_channels,
                "auth_users": auth_users
            }

# Global DB instance
db = Database()

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class User:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    is_authenticated: bool
    active_channel_id: Optional[int]
    auth_date: Optional[str]

@dataclass
class Channel:
    channel_id: int
    title: str
    username: Optional[str]
    invite_link: Optional[str]
    can_post: bool
    is_active: bool
    added_at: str

@dataclass
class UserSettings:
    user_id: int
    silent_mode: bool = False
    preview_mode: bool = True  # Converts doc images/videos to native previewable media
    pdf_mode: str = "banner"    # "banner": HD Cover Photo on top + PDF doc | "document": Single doc with thumb
    pin_post: bool = False
    confirm_mode: bool = False  # Instant send vs ask confirmation
    custom_watermark: Optional[str] = None

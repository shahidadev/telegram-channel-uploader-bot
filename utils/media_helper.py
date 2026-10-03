import os
import logging
from typing import Optional
from aiogram.types import Document, Message

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".tiff", ".svg", ".jfif", ".gif"
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".webm", ".avi", ".flv", ".3gp", ".m4v", ".wmv", ".ts", ".m4p", ".vob"
}
AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".opus", ".wma", ".alac", ".aiff"
}
PDF_EXTENSIONS = {".pdf"}

def get_file_extension(filename: Optional[str]) -> str:
    if not filename:
        return ""
    _, ext = os.path.splitext(filename)
    return ext.lower()

def is_image_document(doc: Document) -> bool:
    """Checks if a Telegram Document is an image."""
    mime = (doc.mime_type or "").lower()
    if mime.startswith("image/"):
        return True
    ext = get_file_extension(doc.file_name)
    return ext in IMAGE_EXTENSIONS

def is_video_document(doc: Document) -> bool:
    """Checks if a Telegram Document is a video."""
    mime = (doc.mime_type or "").lower()
    if mime.startswith("video/"):
        return True
    ext = get_file_extension(doc.file_name)
    return ext in VIDEO_EXTENSIONS

def is_audio_document(doc: Document) -> bool:
    """Checks if a Telegram Document is an audio file."""
    mime = (doc.mime_type or "").lower()
    if mime.startswith("audio/"):
        return True
    ext = get_file_extension(doc.file_name)
    return ext in AUDIO_EXTENSIONS

def is_pdf_document(doc: Document) -> bool:
    """Checks if a Telegram Document is a PDF."""
    mime = (doc.mime_type or "").lower()
    if mime in ("application/pdf", "application/x-pdf", "application/acrobat", "applications/vnd.pdf", "text/pdf", "text/x-pdf"):
        return True
    ext = get_file_extension(doc.file_name)
    return ext in PDF_EXTENSIONS

def format_file_size(size_bytes: int) -> str:
    """Formats bytes to human readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def prepare_caption(message: Message, watermark: Optional[str] = None) -> Optional[str]:
    """
    Prepares the caption or text, appending custom watermark if provided.
    Retains HTML formatting when used with parse_mode='HTML'.
    """
    base_text = message.html_text or message.caption or message.text or ""
    
    if watermark:
        watermark_clean = watermark.strip()
        if base_text:
            return f"{base_text}\n\n{watermark_clean}"
        return watermark_clean
        
    return base_text if base_text else None

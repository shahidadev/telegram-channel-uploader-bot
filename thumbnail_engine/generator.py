import os
import io
import uuid
import tempfile
import logging
from typing import Optional
from PIL import Image, ImageOps, ImageDraw

logger = logging.getLogger(__name__)

# Temporary directory for generated thumbnails
TEMP_DIR = os.path.join(tempfile.gettempdir(), "telegram_uploader_thumbs")
os.makedirs(TEMP_DIR, exist_ok=True)

def get_temp_file_path(extension: str = ".jpg") -> str:
    """Generates a unique temporary file path."""
    filename = f"thumb_{uuid.uuid4().hex[:12]}{extension}"
    return os.path.join(TEMP_DIR, filename)

def cleanup_temp_files(*file_paths: Optional[str]):
    """Safely deletes temporary files from disk."""
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Deleted temporary file: {path}")
            except Exception as e:
                logger.warning(f"Could not delete temporary file {path}: {e}")

def generate_document_thumbnail(
    input_file_path: str,
    output_thumbnail_path: Optional[str] = None,
    max_dim: int = 320
) -> Optional[str]:
    """
    Generates a clean First-Page Screenshot thumbnail from any supported document,
    strictly formatted for Telegram sendDocument (JPEG, max_dim <= 320px, size < 200KB).
    """
    if not os.path.isfile(input_file_path):
        logger.error(f"Input document does not exist: {input_file_path}")
        return None

    if not output_thumbnail_path:
        output_thumbnail_path = get_temp_file_path(".jpg")

    _, ext = os.path.splitext(input_file_path.lower())

    try:
        # 1. PyMuPDF-Supported Documents (PDF, EPUB, XPS, CBZ, CBR, MOBI, FB2, SVG)
        import pymupdf
        try:
            doc = pymupdf.open(input_file_path)
            if len(doc) > 0:
                p0 = doc.load_page(0)
                rect = p0.rect
                scale = min(float(max_dim) / rect.width, float(max_dim) / rect.height)
                mat = pymupdf.Matrix(scale, scale)
                pix = p0.get_pixmap(matrix=mat)
                
                if pix.alpha:
                    mode = "RGBA"
                else:
                    mode = "RGB"
                page_img = Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert("RGB")
                doc.close()

                page_img.save(output_thumbnail_path, format="JPEG", quality=90)
                return output_thumbnail_path
        except Exception as e:
            logger.debug(f"PyMuPDF rendering fallback for {input_file_path}: {e}")

        # 2. Image files sent as document
        try:
            img = Image.open(input_file_path).convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            img.save(output_thumbnail_path, format="JPEG", quality=90)
            return output_thumbnail_path
        except Exception:
            pass

        # 3. Text / Code / Generic readable files
        if ext in (".txt", ".py", ".json", ".csv", ".log", ".md", ".html", ".xml", ".css", ".js", ".rtf", ".ini"):
            try:
                with open(input_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [f.readline() for _ in range(16)]
                
                sheet_w, sheet_h = 240, 320
                sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
                draw = ImageDraw.Draw(sheet)
                
                y_offset = 15
                for line in lines:
                    text_line = line.replace("\t", "  ").rstrip()
                    if text_line:
                        draw.text((15, y_offset), text_line[:30], fill=(40, 40, 40))
                    y_offset += 16
                    if y_offset > sheet_h - 20:
                        break
                        
                border_sheet = ImageOps.expand(sheet, border=1, fill=(210, 210, 210))
                border_sheet.save(output_thumbnail_path, format="JPEG", quality=90)
                return output_thumbnail_path
            except Exception as e:
                logger.debug(f"Text preview generation fallback: {e}")

        # 4. Clean Document Icon Thumbnail Fallback
        sheet_w, sheet_h = 240, 320
        canvas = Image.new("RGB", (sheet_w, sheet_h), (250, 250, 250))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([10, 10, sheet_w - 10, sheet_h - 10], fill=(255, 255, 255), outline=(200, 200, 200), width=1)
        
        clean_ext = ext.replace(".", "").upper() if ext else "FILE"
        draw.rectangle([25, 30, sheet_w - 25, 75], fill=(235, 240, 245))
        draw.text((sheet_w // 2, 52), clean_ext[:5], fill=(40, 50, 60), anchor="mm")
        
        line_y = 100
        for _ in range(6):
            draw.rectangle([25, line_y, sheet_w - 25, line_y + 8], fill=(225, 230, 235))
            line_y += 24

        canvas.save(output_thumbnail_path, format="JPEG", quality=90)
        return output_thumbnail_path

    except Exception as e:
        logger.error(f"Error generating thumbnail for {input_file_path}: {e}", exc_info=True)
        return None

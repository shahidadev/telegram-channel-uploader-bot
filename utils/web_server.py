import logging
import os
from aiohttp import web
from typing import Optional

logger = logging.getLogger(__name__)

async def handle_root(request: web.Request) -> web.Response:
    """Root endpoint for status check."""
    return web.json_response({
        "status": "online",
        "service": "Telegram Channel Media Uploader Bot",
        "version": "1.0.0",
        "message": "Bot is running actively."
    })

async def handle_health(request: web.Request) -> web.Response:
    """Standard HTTP 200 health check endpoint for Render/Uptime monitors."""
    return web.Response(text="OK", status=200, content_type="text/plain")

async def start_web_server(port: int = 8080) -> Optional[web.AppRunner]:
    """Starts a lightweight async HTTP server for Render / Koyeb / Railway port binding."""
    try:
        app = web.Application()
        app.router.add_get("/", handle_root)
        app.router.add_get("/health", handle_health)
        app.router.add_get("/ping", handle_health)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host="0.0.0.0", port=port)
        await site.start()
        logger.info(f"🌐 Health-check web server started on 0.0.0.0:{port}")
        return runner
    except Exception as e:
        logger.error(f"Failed to start health-check web server on port {port}: {e}")
        return None

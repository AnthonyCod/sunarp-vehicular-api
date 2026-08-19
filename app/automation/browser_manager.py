from typing import Optional
from scrapling.engines._browsers._stealth import AsyncStealthySession
from app.config import settings

class BrowserSessionManager:
    def __init__(self):
        self.session: Optional[AsyncStealthySession] = None

    async def initialize(self):
        """
        Inicializa la instancia principal de la sesión de navegación de Scrapling.
        """
        # Usamos la configuración limpia de la sesión sigilosa que evade Turnstile.
        # Evitamos pasar locale y timezone_id específicos para evitar discrepancias
        # de huella digital (fingerprint) detectables por Cloudflare.
        self.session = AsyncStealthySession(
            headless=settings.HEADLESS_MODE,
            proxy=settings.OUTBOUND_PROXY,
            solve_cloudflare=True,
            capture_xhr=".*"
        )
        await self.session.start()

    async def shutdown(self):
        """
        Libera de forma ordenada los recursos del navegador.
        """
        if self.session:
            await self.session.close()
            self.session = None

session_manager = BrowserSessionManager()

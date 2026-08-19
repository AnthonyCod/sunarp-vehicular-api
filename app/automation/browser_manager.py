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
        # max_pages debe cubrir la concurrencia real del pool de páginas del
        # navegador; el default de Scrapling es 1, lo que hacía que consultas
        # concurrentes (limitadas por MAX_CONCURRENT_SESSIONS) compitieran por
        # una sola pestaña y fallaran por timeout aunque la placa existiera.
        self.session = AsyncStealthySession(
            headless=settings.HEADLESS_MODE,
            proxy=settings.OUTBOUND_PROXY,
            solve_cloudflare=True,
            capture_xhr=".*",
            max_pages=settings.MAX_CONCURRENT_SESSIONS
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

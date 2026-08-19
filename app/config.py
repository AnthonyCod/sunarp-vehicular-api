import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings:
    SUNARP_PORTAL_URL: str = "https://consultavehicular.sunarp.gob.pe/consulta-vehicular/inicio"
    HEADLESS_MODE: bool = os.getenv("HEADLESS_MODE", "true").lower() == "true"
    OUTBOUND_PROXY: Optional[str] = os.getenv("OUTBOUND_PROXY", None)
    MAX_CONCURRENT_SESSIONS: int = int(os.getenv("MAX_CONCURRENT_SESSIONS", "3"))
    OPERATION_TIMEOUT: int = int(os.getenv("OPERATION_TIMEOUT", "30"))

settings = Settings()

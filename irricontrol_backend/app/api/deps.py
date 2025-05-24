import httpx
from app.core.config import HTTP_TIMEOUT # Importa do novo local

async def get_http_session():
    async with httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT)) as client:
        yield client
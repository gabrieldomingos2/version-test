import httpx
from core.config import HTTP_TIMEOUT  # ✔️ Import corrigido

async def get_http_session():
    async with httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT)) as client:
        yield client

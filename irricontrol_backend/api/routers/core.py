from typing import List
from fastapi import APIRouter
from core.config import TEMPLATES_DISPONIVEIS
from core.paths import STATIC_IMAGENS_DIR, ARQUIVOS_DIR  # ✅ CERTO

router = APIRouter()

# 🔗 Endpoint para listar os templates disponíveis
@router.get(
    "/templates",
    response_model=List[str],
    tags=["Core"],
    summary="Lista os templates disponíveis",
    description="Retorna uma lista dos IDs de templates disponíveis para simulação na API."
)
def listar_templates_endpoint():
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]

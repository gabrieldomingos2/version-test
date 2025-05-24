from typing import List
from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.core.config import TEMPLATES_DISPONIVEIS # Importa do novo local

router = APIRouter()

@router.get("/templates", response_model=List[str], tags=["Core"]) # Agora 'List' será reconhecido
def listar_templates_endpoint():
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]

@router.get("/icone-torre", tags=["Core"])
def icone_torre_endpoint():
    return FileResponse("static/imagens/cloudrf.png", media_type="image/png")

@router.get("/arquivos_imagens", tags=["Core"])
def listar_arquivos_imagens_endpoint():
    try:
        # É importante que 'os' seja importado se você vai usá-lo aqui.
        # Se 'os' não estiver importado neste arquivo, adicione 'import os' no topo.
        import os 
        base_path = "static/imagens"
        if not os.path.exists(base_path):
            return {"erro": f"Diretório não encontrado: {base_path}"}
        arquivos = os.listdir(base_path)
        pngs = [arq for arq in arquivos if arq.endswith(".png")]
        jsons = [arq for arq in arquivos if arq.endswith(".json")]
        return {"pngs": pngs, "jsons": jsons}
    except Exception as e:
        return {"erro": str(e)}
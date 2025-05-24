from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.core.config import TEMPLATES_DISPONIVEIS # Importa do novo local

router = APIRouter()

@router.get("/templates", response_model=List[str], tags=["Core"])
def listar_templates_endpoint():
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]

@router.get("/icone-torre", tags=["Core"])
def icone_torre_endpoint():
    # Garanta que o caminho para cloudrf.png esteja correto relativo à raiz do projeto onde main.py está.
    # Se main.py está em irricontrol_backend/app/main.py, e static está em irricontrol_backend/static/
    # o caminho seria "../static/imagens/cloudrf.png"
    # Melhor usar caminhos absolutos ou configurar StaticFiles corretamente na app principal.
    # Assumindo que StaticFiles está montado na raiz do projeto backend onde está a pasta static:
    return FileResponse("static/imagens/cloudrf.png", media_type="image/png")

@router.get("/arquivos_imagens", tags=["Core"]) # Endpoint de debug, pode ser removido em produção
def listar_arquivos_imagens_endpoint():
    try:
        base_path = "static/imagens"
        if not os.path.exists(base_path):
            return {"erro": f"Diretório não encontrado: {base_path}"}
        arquivos = os.listdir(base_path)
        pngs = [arq for arq in arquivos if arq.endswith(".png")]
        jsons = [arq for arq in arquivos if arq.endswith(".json")]
        return {"pngs": pngs, "jsons": jsons}
    except Exception as e:
        return {"erro": str(e)}
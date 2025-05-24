from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# ✅ Importando os routers
from app.api.routers import core, kmz, simulation

# ============================
# ✅ Instância do FastAPI
# ============================
app = FastAPI(
    title="Irricontrol Simulador API",
    version="1.0.0",
    description="🚀 API oficial do Simulador de Sinal Irricontrol",
)

# ============================
# ✅ CORS (liberação de frontends autorizados)
# ============================
allowed_origins = [
    "https://irricontrol-test.netlify.app",
]

if os.getenv("FASTAPI_ENV", "production") == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:5500"
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# ✅ Diretórios e arquivos
# ============================

# Pega o diretório RAIZ do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Diretório dos arquivos estáticos (imagens, ícones, etc.)
STATIC_DIR = os.path.join(BASE_DIR, "irricontrol_backend", "app", "static")

# Diretório dos arquivos temporários (KMZ, PNG, etc.)
ARQUIVOS_DIR_MAIN = os.path.join(BASE_DIR, "irricontrol_backend", "arquivos")

# Cria as pastas caso não existam
os.makedirs(os.path.join(STATIC_DIR, "imagens"), exist_ok=True)
os.makedirs(ARQUIVOS_DIR_MAIN, exist_ok=True)

print(f"🗂️ STATIC_DIR → {STATIC_DIR}")
print(f"🗂️ ARQUIVOS_DIR_MAIN → {ARQUIVOS_DIR_MAIN}")

# ============================
# ✅ Montagem dos arquivos estáticos
# ============================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ============================
# ✅ Rotas da API
# ============================
app.include_router(core.router, prefix="/core", tags=["Core"])
app.include_router(kmz.router, prefix="/kmz", tags=["KMZ"])
app.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])

# ============================
# ✅ Endpoint raiz
# ============================
@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": "🚀 Bem-vindo à API do Simulador Irricontrol",
        "status": "🟢 Online",
        "docs": "/docs",
        "static_example": "/static/imagens/seu_arquivo.png",
    }

# ============================
# ✅ Execução direta local (opcional)
# ============================
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

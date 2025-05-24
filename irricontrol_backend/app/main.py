from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Importando os routers
from app.api.routers import core, kmz, simulation

# ========================
# ✅ Instância do FastAPI
# ========================
app = FastAPI(
    title="Irricontrol Simulador API",
    version="1.0.0"
)

# =========================
# ✅ Configurações de CORS
# =========================
allowed_origins = [
    "https://irricontrol-test.netlify.app",  # Frontend Netlify produção
]

# Adiciona origens locais se for desenvolvimento
if os.getenv("FASTAPI_ENV", "production") == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:5500"
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)),  # Remove duplicatas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# ✅ Diretórios e arquivos
# ============================

# 📁 Diretório estático (imagens, ícones, etc.)
STATIC_DIR = "app/static"

if not os.path.exists(STATIC_DIR):
    os.makedirs(os.path.join(STATIC_DIR, "imagens"), exist_ok=True)
    print(f"✅ Diretório de estáticos criado em: {os.path.abspath(STATIC_DIR)}")

# Montando arquivos estáticos na rota '/static'
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 📁 Diretório para arquivos de entrada e saída (KMZ, PNG, etc.)
ARQUIVOS_DIR_MAIN = "arquivos"
if not os.path.exists(ARQUIVOS_DIR_MAIN):
    os.makedirs(ARQUIVOS_DIR_MAIN)
    print(f"✅ Diretório de arquivos criado em: {os.path.abspath(ARQUIVOS_DIR_MAIN)}")

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
    return {"message": "🚀 Bem-vindo à API do Simulador Irricontrol"}

# ============================
# ✅ Execução direta (opcional)
# ============================
# Descomente se quiser rodar direto com 'python main.py'
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

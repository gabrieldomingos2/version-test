from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ✅ Imports organizados
from api.routers import core, kmz, simulation
from core.paths import STATIC_DIR, ARQUIVOS_DIR

# ✅ Instância do FastAPI
app = FastAPI(
    title="Irricontrol Simulador API",
    version="1.0.0",
    description="🚀 API oficial do Simulador de Sinal Irricontrol",
)

# ✅ CORS
allowed_origins = [
    "https://irricontrol-test.netlify.app",
]

if os.getenv("FASTAPI_ENV", "production") == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Montagem dos arquivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ✅ Rotas
app.include_router(core.router, prefix="/core", tags=["Core"])
app.include_router(kmz.router, prefix="/kmz", tags=["KMZ"])
app.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])

# ✅ Endpoint raiz
@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": "🚀 Bem-vindo à API do Simulador Irricontrol",
        "status": "🟢 Online",
        "docs": "/docs",
        "static_check": f"Verifique se você pode acessar: /static/imagens/NOME_DA_SUA_IMAGEM.png",
    }

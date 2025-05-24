from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Importando os routers
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

# Permite origens locais se estiver em ambiente de desenvolvimento
if os.getenv("FASTAPI_ENV", "production") == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:5500",
        "http://localhost:5500" # Adicionado por segurança
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)), # Garante origens únicas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# ✅ Diretórios e arquivos
# ============================

# Pega o diretório ONDE ESTE ARQUIVO (main.py) está
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Sobe um nível para chegar ao diretório RAIZ do projeto (onde 'app', 'static', 'arquivos' devem estar)
# Se sua estrutura for diferente, ajuste esta linha!
PROJECT_ROOT = os.path.dirname(APP_DIR) 

# --- CORREÇÃO APLICADA AQUI ---
# Aponta para a pasta 'static' na RAIZ do projeto
STATIC_DIR = os.path.join(PROJECT_ROOT, "static") 
# Aponta para a pasta 'arquivos' na RAIZ do projeto
ARQUIVOS_DIR_MAIN = os.path.join(PROJECT_ROOT, "arquivos")
# --- FIM DA CORREÇÃO ---


# Cria as pastas caso não existam
# É crucial que o processo que SALVA as imagens use EXATAMENTE este 'STATIC_DIR'
os.makedirs(os.path.join(STATIC_DIR, "imagens"), exist_ok=True)
os.makedirs(ARQUIVOS_DIR_MAIN, exist_ok=True)

# Imprime os caminhos para depuração ao iniciar o servidor
print(f"🗂️ PROJECT_ROOT → {PROJECT_ROOT}")
print(f"🗂️ STATIC_DIR (usado para servir) → {STATIC_DIR}")
print(f"🗂️ ARQUIVOS_DIR_MAIN (usado para uploads) → {ARQUIVOS_DIR_MAIN}")

# ============================
# ✅ Montagem dos arquivos estáticos
# ============================
# Diz ao FastAPI: "Quando o navegador pedir '/static/...', 
# procure os arquivos dentro do diretório definido em STATIC_DIR."
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
        "static_check": f"Verifique se você pode acessar: /static/imagens/NOME_DA_SUA_IMAGEM.png",
    }

# ============================
# ✅ Execução direta local (opcional)
# ============================
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
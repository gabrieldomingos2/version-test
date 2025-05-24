from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os # Necessário para StaticFiles e outras operações de path

# Importar routers
from app.api.routers import core, kmz, simulation
# Importar configurações (para o API_KEY, mas ele é usado dentro dos routers/serviços agora)
# from app.core.config import API_KEY # Não precisa mais aqui se usado diretamente nos módulos

app = FastAPI(title="Irricontrol Simulador API", version="1.0.0")

# Configuração de CORS
# Para desenvolvimento, pode ser útil adicionar "http://localhost:xxxx" (porta do seu frontend dev)
# ou "http://127.0.0.1:xxxx"
allowed_origins = [
    "https://irricontrol-test.netlify.app", # Sua URL de produção no Netlify
    # Adicione URLs de desenvolvimento aqui, se necessário:
    # "http://localhost:8000", # Exemplo se seu frontend local roda na porta 8000
    # "http://127.0.0.1:5500", # Exemplo para Live Server do VSCode
]

# Em um ambiente de desenvolvimento, você pode querer ser mais permissivo:
if os.getenv("FASTAPI_ENV", "production") == "development":
    allowed_origins.extend([
        "http://localhost:3000", # React comum
        "http://localhost:8000", # Python http.server
        "http://localhost:8080", # Vue comum
        "http://127.0.0.1:5500"  # Live Server VSCode
    ])
    # Para desenvolvimento extremo, pode usar ["*"], mas não recomendado para produção.

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)), # Remove duplicatas se houver
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar diretório estático
# O path para 'directory' deve ser relativo à localização de onde você RODA o uvicorn.
# Se você roda uvicorn da pasta 'irricontrol_backend/', e 'static' está dentro de 'irricontrol_backend/static',
# então o path é simplesmente "static".
# Se 'static' está em 'irricontrol_backend/app/static', seria "app/static".
# Baseado no seu código original, parece que 'static' está na raiz do projeto backend.
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
    os.makedirs(os.path.join(STATIC_DIR, "imagens"), exist_ok=True) # Garante que imagens exista
    print(f"Diretório estático criado em: {os.path.abspath(STATIC_DIR)}")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Cria o diretório 'arquivos' se não existir, relativo à raiz do projeto
ARQUIVOS_DIR_MAIN = "arquivos"
if not os.path.exists(ARQUIVOS_DIR_MAIN):
    os.makedirs(ARQUIVOS_DIR_MAIN)
    print(f"Diretório de arquivos criado em: {os.path.abspath(ARQUIVOS_DIR_MAIN)}")


# Incluir routers
app.include_router(core.router, prefix="/core", tags=["Core"]) # Adicionando prefixo para organização
app.include_router(kmz.router, prefix="/kmz", tags=["KMZ"])
app.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])


# Endpoint raiz simples
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Bem-vindo à API do Simulador Irricontrol"}

# Exemplo de como rodar (coloque no final do arquivo se for rodar com 'python main.py'):
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
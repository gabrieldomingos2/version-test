import os

# Diretório raiz do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Diretório de arquivos estáticos (imagens)
STATIC_DIR = os.path.join(BASE_DIR, "static")
STATIC_IMAGENS_DIR = os.path.join(STATIC_DIR, "imagens")

# Diretório de arquivos temporários
ARQUIVOS_DIR = os.path.join(BASE_DIR, "arquivos")

# Garante que as pastas existem
os.makedirs(STATIC_IMAGENS_DIR, exist_ok=True)
os.makedirs(ARQUIVOS_DIR, exist_ok=True)

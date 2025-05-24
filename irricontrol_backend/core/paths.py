import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))  # Pasta core
PROJECT_ROOT = os.path.dirname(APP_DIR)               # Pasta raiz (onde está main.py)

STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
ARQUIVOS_DIR = os.path.join(PROJECT_ROOT, "arquivos")

# Cria pastas se não existirem
os.makedirs(os.path.join(STATIC_DIR, "imagens"), exist_ok=True)
os.makedirs(ARQUIVOS_DIR, exist_ok=True)

# Debug opcional
print(f"🗂️ STATIC_DIR → {STATIC_DIR}")
print(f"🗂️ ARQUIVOS_DIR → {ARQUIVOS_DIR}")

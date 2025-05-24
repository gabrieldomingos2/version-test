import os
from dotenv import load_dotenv

load_dotenv() # Carrega variáveis de .env se existir (para desenvolvimento local)

API_URL = "https://api.cloudrf.com/area"
API_KEY = os.getenv("CLOUDRF_API_KEY", "35113-e181126d4af70994359d767890b3a4f2604eb0ef") # Fallback para a chave antiga se não definida no env
HTTP_TIMEOUT = 60.0

# Templates disponíveis no sistema
TEMPLATES_DISPONIVEIS = [
    {
        "id": "Brazil_V6", "nome": "🇧🇷 Brazil V6", "frq": 915, "col": "IRRICONTRO.dBm",
        "site": "Brazil_V6", "rxs": -90,
        "transmitter": {"txw": 0.3, "bwi": 0.1},
        "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -90},
        "antenna": {"txg": 3, "fbr": 3}
    },
    {
        "id": "Europe_V6_XR", "nome": "🇪🇺 Europe V6 XR", "frq": 868, "col": "IRRIEUROPE.dBm",
        "site": "V6_XR.dBm", "rxs": -105,
        "transmitter": {"txw": 0.02, "bwi": 0.05},
        "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 2.1, "rxs": -105},
        "antenna": {"txg": 2.1, "fbr": 2.1}
    }
]

def obter_template(template_id: str):
    template = next((t for t in TEMPLATES_DISPONIVEIS if t["id"] == template_id), None)
    if not template:
        raise ValueError(f"Template '{template_id}' não encontrado.")
    return template

# Crie um arquivo .env na raiz do projeto backend com:
# CLOUDRF_API_KEY=sua_outra_api_key_se_tiver
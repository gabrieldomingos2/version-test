import re

def normalizar_nome(nome: str) -> str:
    if not nome:
        return ""
    return re.sub(r'[^a-z0-9]', '', nome.lower())

def format_coord(coord: float) -> str:
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")
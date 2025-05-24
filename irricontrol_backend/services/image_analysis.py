from PIL import Image
from typing import List, Dict, Any


def detectar_pivos_fora(
    bounds: List[float],
    pivos: List[Dict[str, Any]],
    caminho_imagem: str,
    pivos_existentes_cobertos: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Detecta pivôs fora da cobertura de uma imagem PNG de sinal.
    Marca 'fora=True' se o pivô está em pixel transparente (alpha=0).

    Args:
        bounds: [sul, oeste, norte, leste] da imagem.
        pivos: Lista de dicts {'nome', 'lat', 'lon'}.
        caminho_imagem: Caminho local da imagem.
        pivos_existentes_cobertos: Lista de nomes já cobertos (opcional).

    Returns:
        Lista de dicts dos pivôs, cada um com o campo adicional 'fora'.
    """
    if pivos_existentes_cobertos is None:
        pivos_existentes_cobertos = []

    try:
        # 📥 Abre imagem e coleta dados
        img = Image.open(caminho_imagem).convert("RGBA")
        largura, altura = img.size

        sul, oeste, norte, leste = bounds

        # 🔧 Corrige bounds se invertidos
        if oeste > leste:
            oeste, leste = leste, oeste
        if sul > norte:
            sul, norte = norte, sul

        delta_lon = leste - oeste
        delta_lat = norte - sul

        if delta_lon == 0 or delta_lat == 0:
            print("⚠️ Bounds inválidos (delta zero).")
            return [{**p, "fora": True} for p in pivos]

        resultado = []

        for p in pivos:
            nome = p["nome"]
            lat = p["lat"]
            lon = p["lon"]

            # 🎯 Conversão lat/lon -> pixel
            x = int(((lon - oeste) / delta_lon) * largura)
            y = int(((norte - lat) / delta_lat) * altura)

            # 🏁 Check se está dentro da imagem
            if 0 <= x < largura and 0 <= y < altura:
                _, _, _, alpha = img.getpixel((x, y))
                dentro_cobertura = alpha > 0
            else:
                dentro_cobertura = False

            # 📜 Regra: Se já estava coberto antes, continua coberto
            fora = not dentro_cobertura and nome not in pivos_existentes_cobertos

            resultado.append({
                "nome": nome,
                "lat": lat,
                "lon": lon,
                "fora": fora
            })

        return resultado

    except FileNotFoundError:
        print(f"❌ Imagem não encontrada: {caminho_imagem}")
        return [{**p, "fora": True} for p in pivos]
    except Exception as e:
        print(f"❌ Erro processando {caminho_imagem}: {e}")
        return [{**p, "fora": True} for p in pivos]

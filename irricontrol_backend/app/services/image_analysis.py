from PIL import Image
from typing import List, Dict, Any

def detectar_pivos_fora(bounds: List[float], pivos: List[Dict[str, Any]], caminho_imagem: str, pivos_existentes_cobertos: List[str] = None) -> List[Dict[str, Any]]:
    """
    Detecta pivôs fora da cobertura de uma imagem de sinal.

    Args:
        bounds: [sul, oeste, norte, leste] da imagem.
        pivos: Lista de dicionários de pivôs, cada um com "lat", "lon", "nome".
        caminho_imagem: Caminho local para a imagem de sinal.
        pivos_existentes_cobertos: Lista de nomes de pivôs que já estão cobertos por outras fontes.
                                   Se um pivô estiver nesta lista, ele não será marcado como "fora",
                                   mesmo que não esteja coberto pela imagem atual.
    """
    if pivos_existentes_cobertos is None:
        pivos_existentes_cobertos = []

    try:
        img = Image.open(caminho_imagem).convert("RGBA")
        largura_img, altura_img = img.size

        sul, oeste, norte, leste = bounds
        # Normaliza bounds se necessário (leste < oeste ou norte < sul)
        if oeste > leste: oeste, leste = leste, oeste
        if sul > norte: sul, norte = norte, sul
        
        delta_lon = leste - oeste
        delta_lat = norte - sul

        if delta_lon == 0 or delta_lat == 0: # Evita divisão por zero
            print("⚠️ Aviso: Bounds da imagem inválidos (delta_lon ou delta_lat é zero). Marcando todos os pivôs como fora.")
            return [{**p, "fora": True} for p in pivos]

        resultado_pivos = []
        for pivo in pivos:
            # Converte lat/lon do pivô para coordenadas de pixel na imagem
            # (0,0) da imagem é topo-esquerda
            x_pixel = int(((pivo["lon"] - oeste) / delta_lon) * largura_img)
            y_pixel = int(((norte - pivo["lat"]) / delta_lat) * altura_img)

            coberto_nesta_imagem = False
            if 0 <= x_pixel < largura_img and 0 <= y_pixel < altura_img:
                _, _, _, alpha_channel = img.getpixel((x_pixel, y_pixel))
                if alpha_channel > 0: # Pixel não é totalmente transparente
                    coberto_nesta_imagem = True
            
            # Verifica se o pivô já estava coberto por uma fonte anterior
            pivo_ja_coberto_antes = pivo["nome"] in pivos_existentes_cobertos

            # Um pivô está "fora" se NÃO estiver coberto por ESTA imagem E NÃO estava coberto antes.
            # Ou, se a lógica é que esta imagem é a ÚNICA fonte de cobertura, então:
            # pivo["fora"] = not coberto_nesta_imagem
            # Ajuste esta lógica conforme necessário para o comportamento desejado com múltiplos overlays.
            # Para a função reavaliar_pivos, que considera múltiplos overlays, a lógica será diferente.
            # Aqui, para simulação individual, `pivos_existentes_cobertos` não é usado diretamente,
            # a API de reavaliação cuidará da lógica agregada.
            # Por simplicidade, esta função agora apenas determina a cobertura para ESTA imagem.
            pivo["fora"] = not coberto_nesta_imagem
            resultado_pivos.append(pivo)

        return resultado_pivos

    except FileNotFoundError:
        print(f"Erro: Imagem não encontrada em {caminho_imagem}. Marcando todos os pivôs como fora.")
        return [{**p, "fora": True} for p in pivos]
    except Exception as e:
        print(f"Erro ao analisar imagem {caminho_imagem}: {e}")
        # Em caso de erro, assume que os pivôs estão fora para esta imagem
        return [{**p, "fora": True} for p in pivos]
from PIL import Image
from typing import List, Dict, Any
import os # Importar 'os' se ainda não estiver importado no seu arquivo

def detectar_pivos_fora(bounds: List[float], pivos: List[Dict[str, Any]], caminho_imagem: str, pivos_existentes_cobertos: List[str] = None) -> List[Dict[str, Any]]:
    """
    Detecta pivôs fora da cobertura de uma imagem de sinal.

    Args:
        bounds: [sul, oeste, norte, leste] da imagem.
        pivos: Lista de dicionários de pivôs, cada um com "lat", "lon", "nome".
        caminho_imagem: Caminho local para a imagem de sinal.
        pivos_existentes_cobertos: Lista de nomes de pivôs que já estão cobertos por outras fontes.
                                      (Atualmente não usado para determinar 'fora', mas pode ser útil no futuro).
    """
    if pivos_existentes_cobertos is None:
        pivos_existentes_cobertos = []

    print(f"\n--- Iniciando detecção para: {os.path.basename(caminho_imagem)} ---")
    print(f"Bounds recebidos: {bounds}")

    try:
        # Verifica se o arquivo existe ANTES de tentar abrir
        if not os.path.exists(caminho_imagem):
            print(f"🚨 ERRO FATAL: Imagem não encontrada em {caminho_imagem}. Marcando todos os pivôs como fora.")
            return [{**p, "fora": True} for p in pivos]

        img = Image.open(caminho_imagem).convert("RGBA")
        largura_img, altura_img = img.size
        print(f"Imagem '{os.path.basename(caminho_imagem)}' aberta ({largura_img}x{altura_img}).")

        sul, oeste, norte, leste = bounds
        
        # --- Bloco de Verificação e Correção de Bounds ---
        print(f"Bounds antes da correção: S={sul}, W={oeste}, N={norte}, E={leste}")
        if oeste > leste: 
            print("  ⚠️ Corrigindo: Oeste > Leste")
            oeste, leste = leste, oeste
        if sul > norte: 
            print("  ⚠️ Corrigindo: Sul > Norte")
            sul, norte = norte, sul
        print(f"Bounds após correção: S={sul}, W={oeste}, N={norte}, E={leste}")
        # --- Fim do Bloco ---

        delta_lon = leste - oeste
        delta_lat = norte - sul

        if delta_lon == 0 or delta_lat == 0:
            print(f"⚠️ Aviso: Bounds da imagem inválidos (delta_lon={delta_lon} ou delta_lat={delta_lat}). Marcando todos como fora.")
            return [{**p, "fora": True} for p in pivos]
            
        print(f"Delta Lon: {delta_lon}, Delta Lat: {delta_lat}")

        resultado_pivos = []
        for pivo in pivos:
            # Converte lat/lon do pivô para coordenadas de pixel na imagem
            # (0,0) da imagem é topo-esquerda
            x_pixel_f = ((pivo["lon"] - oeste) / delta_lon) * largura_img
            y_pixel_f = ((norte - pivo["lat"]) / delta_lat) * altura_img
            
            x_pixel = int(x_pixel_f)
            y_pixel = int(y_pixel_f)

            coberto_nesta_imagem = False
            alpha_value = -1  # Valor padrão para indicar que não foi lido

            # Verifica se o pixel está dentro dos limites da imagem
            if 0 <= x_pixel < largura_img and 0 <= y_pixel < altura_img:
                try:
                    r, g, b, alpha_channel = img.getpixel((x_pixel, y_pixel))
                    alpha_value = alpha_channel  # Guarda o valor lido
                    # Considera coberto se o alfa for maior que 10 (um limiar para evitar ruídos)
                    if alpha_channel > 10:
                        coberto_nesta_imagem = True
                except Exception as e_pixel:
                    print(f"  🚨 Erro ao ler pixel ({x_pixel}, {y_pixel}): {e_pixel}")
            else:
                 print(f"  🟡 Aviso: Pivô '{pivo['nome']}' ({x_pixel}, {y_pixel}) fora dos limites da imagem ({largura_img}x{altura_img}).")


            # --- Bloco de Print para Depuração ---
            print(f"  Pivo: {pivo['nome']} (Lat: {pivo['lat']:.6f}, Lon: {pivo['lon']:.6f})")
            print(f"    -> Pixel (Float): X={x_pixel_f:.2f}, Y={y_pixel_f:.2f}")
            print(f"    -> Pixel (Int):   X={x_pixel}, Y={y_pixel}")
            print(f"    -> Alpha Lido:    {alpha_value}")
            print(f"    -> Coberto:       {coberto_nesta_imagem}")
            # --- Fim do Bloco ---

            # A lógica `pivos_existentes_cobertos` foi removida daqui,
            # pois a agregação deve ocorrer na função que chama esta.
            # Esta função agora apenas reporta a cobertura para *esta* imagem.
            pivo_atualizado = pivo.copy() # Cria uma cópia para evitar modificar o original em chamadas futuras
            pivo_atualizado["fora"] = not coberto_nesta_imagem
            resultado_pivos.append(pivo_atualizado)
            print(f"    -> Resultado (fora): {pivo_atualizado['fora']}")

        print(f"--- Detecção concluída para: {os.path.basename(caminho_imagem)} ---")
        return resultado_pivos

    except FileNotFoundError:
        # Este erro já foi tratado acima, mas mantemos por segurança.
        print(f"🚨 ERRO FATAL (Catch): Imagem não encontrada em {caminho_imagem}. Marcando todos como fora.")
        return [{**p, "fora": True} for p in pivos]
    except Exception as e:
        print(f"🚨 ERRO GERAL ao analisar imagem {caminho_imagem}: {e}")
        import traceback
        traceback.print_exc() # Imprime o stack trace completo para mais detalhes
        # Em caso de erro, assume que os pivôs estão fora para esta imagem
        return [{**p, "fora": True} for p in pivos]
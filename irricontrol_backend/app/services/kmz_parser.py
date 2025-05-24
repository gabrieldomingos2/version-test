import os
import zipfile
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon
from math import sqrt
from typing import List, Tuple, Dict, Any, Optional
from app.utils.file_helpers import normalizar_nome # Importa do novo local
import re

# Estruturas de dados para clareza
AntenaDict = Dict[str, Any]
PivoDict = Dict[str, Any]
CicloDict = Dict[str, Any]
BombaDict = Dict[str, Any]

def parse_kmz(caminho_kmz: str) -> Tuple[Optional[AntenaDict], List[PivoDict], List[CicloDict], List[BombaDict]]:
    antena: Optional[AntenaDict] = None
    pivos: List[PivoDict] = []
    ciclos: List[CicloDict] = []
    bombas: List[BombaDict] = []

    # Cria a pasta 'arquivos' se não existir para extração
    os.makedirs("arquivos", exist_ok=True)

    with zipfile.ZipFile(caminho_kmz, 'r') as kmz_file:
        for nome_arquivo_interno in kmz_file.namelist():
            if nome_arquivo_interno.endswith('.kml'):
                # Extrai para uma subpasta temporária dentro de 'arquivos'
                extract_path = os.path.join("arquivos", "temp_kml_extract")
                os.makedirs(extract_path, exist_ok=True)
                kmz_file.extract(nome_arquivo_interno, extract_path)
                caminho_kml_extraido = os.path.join(extract_path, nome_arquivo_interno)

                tree = ET.parse(caminho_kml_extraido)
                root = tree.getroot()
                ns = {"kml": "http://www.opengis.net/kml/2.2"}

                for placemark in root.findall(".//kml:Placemark", ns):
                    nome_element = placemark.find("kml:name", ns)
                    ponto_element = placemark.find(".//kml:Point/kml:coordinates", ns)
                    linha_element = placemark.find(".//kml:LineString/kml:coordinates", ns) # Para os círculos

                    nome_texto_original = nome_element.text if nome_element is not None else ""
                    nome_texto_lower = nome_texto_original.lower()

                    if ponto_element is not None:
                        coords_str = ponto_element.text.strip().split(",")
                        if len(coords_str) < 2:
                            continue
                        lon, lat = float(coords_str[0]), float(coords_str[1])

                        if any(keyword in nome_texto_lower for keyword in ["antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]):
                            match = re.search(r"(\d{1,3})\s*(m|metros)", nome_texto_lower)
                            altura = int(match.group(1)) if match else 15
                            antena = {"lat": lat, "lon": lon, "altura": altura, "altura_receiver": 3, "nome": nome_texto_original.strip()}
                        elif "pivô" in nome_texto_lower or re.match(r"p\s?\d+", nome_texto_lower):
                            nome_formatado = nome_texto_original.strip()
                            nome_norm = normalizar_nome(nome_formatado)
                            # Adiciona apenas se um pivô com nome normalizado similar ainda não existir
                            if not any(normalizar_nome(p["nome"]) == nome_norm for p in pivos):
                                pivos.append({"nome": nome_formatado, "lat": lat, "lon": lon})
                        elif "casa de bomba" in nome_texto_lower or "irripump" in nome_texto_lower:
                            bombas.append({"nome": nome_texto_original.strip(), "lat": lat, "lon": lon})

                    # Processa LineStrings que representam os círculos (geralmente nomeados como "medida do círculo")
                    if linha_element is not None and "medida do círculo" in nome_texto_lower:
                        coords_texto_list = linha_element.text.strip().split()
                        coords_list = []
                        for c_str in coords_texto_list:
                            partes = c_str.split(",")
                            if len(partes) >= 2:
                                coords_list.append([float(partes[1]), float(partes[0])]) # lat, lon
                        if coords_list: # Adiciona apenas se houver coordenadas válidas
                            ciclos.append({"nome": nome_texto_original.strip(), "coordenadas": coords_list})
                
                # Limpar o KML extraído após o parse
                try:
                    os.remove(caminho_kml_extraido)
                    if not os.listdir(extract_path): # Tenta remover a pasta de extração se estiver vazia
                        os.rmdir(extract_path)
                except OSError as e:
                    print(f"Aviso: não foi possível limpar {caminho_kml_extraido} ou {extract_path}: {e}")

    # Processa círculos para criar pivôs se não existirem Placemarks correspondentes
    nomes_pivos_existentes_norm = {normalizar_nome(p["nome"]) for p in pivos}
    pivo_sequencial_idx = 1  # Contador para nomes sequenciais "Pivô 01", "Pivô 02", etc.
    novos_pivos_de_circulos = []

    for ciclo in ciclos:
        nome_ciclo_original = ciclo.get("nome", "").strip() # Nome original do Placemark do círculo
        coords_ciclo = ciclo.get("coordenadas", [])
        
        if not coords_ciclo: # Pula se o círculo não tiver coordenadas
            continue

        # Calcula centroide do ciclo
        try:
            # As coordenadas já estão como [lat, lon], então para shapely (lon, lat)
            coords_lonlat_ciclo = [(lon, lat) for lat, lon in coords_ciclo]
            num_pontos_ciclo = len(coords_lonlat_ciclo)

            if num_pontos_ciclo == 0: # Segurança extra
                print(f"⚠️ Círculo '{nome_ciclo_original}' sem coordenadas para calcular centroide.")
                continue
            elif num_pontos_ciclo == 1: # Se for apenas um ponto, usa ele mesmo
                 centro_lon, centro_lat = coords_lonlat_ciclo[0]
            elif num_pontos_ciclo == 2: # Linha, calcula ponto médio
                p_a, p_b = coords_lonlat_ciclo
                centro_lon, centro_lat = (p_a[0] + p_b[0]) / 2, (p_a[1] + p_b[1]) / 2
            else: # 3 ou mais pontos, calcula centroide do polígono
                poligono = Polygon(coords_lonlat_ciclo)
                centroide_geom = poligono.centroid
                centro_lat, centro_lon = centroide_geom.y, centroide_geom.x
        except Exception as e:
            print(f"⚠️ Erro ao calcular centroide para o círculo '{nome_ciclo_original}', usando média das coordenadas: {e}")
            if not coords_ciclo: continue # Segurança
            centro_lat = mean([lat for lat, lon in coords_ciclo])
            centro_lon = mean([lon for lat, lon in coords_ciclo])

        # Verifica se um pivô já existe (de um Placemark) com nome similar ao do círculo ou por proximidade
        match_encontrado = False
        
        # Tentativa 1: Verificar se o nome do círculo (após limpeza) corresponde a um pivô existente
        # Ex: Círculo "Medida do círculo Pivô Alpha" -> nome_base_pivo_do_circulo = "Pivô Alpha"
        nome_base_pivo_do_circulo = nome_ciclo_original.lower().replace("medida do círculo", "").strip()
        
        nome_pivo_normalizado_do_circulo = ""
        if nome_base_pivo_do_circulo: # Procede apenas se houver um nome base
            nome_pivo_normalizado_do_circulo = normalizar_nome(nome_base_pivo_do_circulo)

        if nome_pivo_normalizado_do_circulo and nome_pivo_normalizado_do_circulo in nomes_pivos_existentes_norm:
            match_encontrado = True
            # print(f"[DEBUG] Círculo '{nome_ciclo_original}' corresponde ao pivô existente '{nome_base_pivo_do_circulo}' pelo nome.")
        
        # Tentativa 2: Se não houve match pelo nome derivado do círculo, verificar por proximidade com pivôs de Placemarks
        if not match_encontrado:
            distancia_min_para_match = 0.0002 # Aproximadamente 22 metros em graus decimais (varia com latitude)
            for pivo_existente in pivos: # 'pivos' aqui contém apenas os de Placemarks até este ponto
                dist = sqrt((pivo_existente["lat"] - centro_lat)**2 + (pivo_existente["lon"] - centro_lon)**2)
                if dist < distancia_min_para_match:
                    match_encontrado = True
                    # print(f"[DEBUG] Círculo '{nome_ciclo_original}' corresponde ao pivô existente '{pivo_existente['nome']}' por proximidade.")
                    break
        
        if not match_encontrado:
            # Este círculo não corresponde a nenhum pivô existente (de Placemark).
            # Criar um novo pivô com nome sequencial "Pivô XX".
            nome_novo_pivo = f"Pivô {pivo_sequencial_idx:02d}"
            
            # Garantir que este nome sequencial também não colida com algum nome já existente (de Placemark ou outro sequencial)
            while normalizar_nome(nome_novo_pivo) in nomes_pivos_existentes_norm:
                pivo_sequencial_idx += 1
                nome_novo_pivo = f"Pivô {pivo_sequencial_idx:02d}"

            novos_pivos_de_circulos.append({
                "nome": nome_novo_pivo, 
                "lat": centro_lat, 
                "lon": centro_lon
            })
            # Adiciona o nome normalizado do novo pivô ao conjunto para evitar colisões futuras nesta mesma execução
            nomes_pivos_existentes_norm.add(normalizar_nome(nome_novo_pivo)) 
            print(f"[DEBUG] Novo Pivô (a partir de círculo '{nome_ciclo_original}') Adicionado: {nome_novo_pivo} → Lat: {centro_lat:.6f}, Lon: {centro_lon:.6f}")
            pivo_sequencial_idx += 1

    pivos.extend(novos_pivos_de_circulos)
    return antena, pivos, ciclos, bombas

# Exemplo de como a função normalizar_nome poderia ser (se não estiver definida em app.utils.file_helpers)
# def normalizar_nome(nome: str) -> str:
#     if nome is None:
#         return ""
#     # Remove acentos, converte para minúsculas, remove espaços extras e caracteres especiais exceto números e letras
#     import unicodedata
#     nome = ''.join(c for c in unicodedata.normalize('NFKD', nome) if unicodedata.category(c) != 'Mn')
#     nome = nome.lower()
#     nome = re.sub(r'[^a-z0-9]+', '', nome)
#     return nome.strip()
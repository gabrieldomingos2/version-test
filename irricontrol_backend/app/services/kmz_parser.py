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
                # Extrai para uma subpasta temporária dentro de 'arquivos' para evitar conflitos
                # e facilitar a limpeza se necessário.
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
                    linha_element = placemark.find(".//kml:LineString/kml:coordinates", ns)

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
                            if not any(normalizar_nome(p["nome"]) == nome_norm for p in pivos):
                                pivos.append({"nome": nome_formatado, "lat": lat, "lon": lon})
                        elif "casa de bomba" in nome_texto_lower or "irripump" in nome_texto_lower:
                            bombas.append({"nome": nome_texto_original.strip(), "lat": lat, "lon": lon})

                    if linha_element is not None and "medida do círculo" in nome_texto_lower:
                        coords_texto_list = linha_element.text.strip().split()
                        coords_list = []
                        for c_str in coords_texto_list:
                            partes = c_str.split(",")
                            if len(partes) >= 2:
                                coords_list.append([float(partes[1]), float(partes[0])]) # lat, lon
                        ciclos.append({"nome": nome_texto_original.strip(), "coordenadas": coords_list})
                
                # Limpar o KML extraído após o parse (opcional, mas bom para higiene)
                try:
                    os.remove(caminho_kml_extraido)
                    # Tentar remover a pasta de extração se estiver vazia
                    if not os.listdir(extract_path):
                        os.rmdir(extract_path)
                except OSError as e:
                    print(f"Aviso: não foi possível limpar {caminho_kml_extraido} ou {extract_path}: {e}")


    # Cria pivôs virtuais
    nomes_pivos_existentes_norm = {normalizar_nome(p["nome"]) for p in pivos}
    contador_virtual = 1
    novos_pivos_virtuais = []

    for ciclo in ciclos:
        nome_ciclo = ciclo.get("nome", "").strip()
        coords_ciclo = ciclo.get("coordenadas", [])
        if not nome_ciclo or not coords_ciclo:
            continue

        nome_base_pivo = nome_ciclo.lower().replace("medida do círculo", "").strip()
        nome_pivo_normalizado_tentativa = normalizar_nome(nome_base_pivo)
        
        # Tenta encontrar um nome de pivô que corresponda ao círculo
        nome_virtual_pivo = f"Pivô {nome_base_pivo.title()}" if nome_base_pivo else f"Pivô Virtual {contador_virtual}"


        # Calcula centroide
        try:
            coords_lonlat_ciclo = [(lon, lat) for lat, lon in coords_ciclo]
            num_pontos_ciclo = len(coords_lonlat_ciclo)
            if num_pontos_ciclo == 2:
                p_a, p_b = coords_lonlat_ciclo
                centro_lon, centro_lat = (p_a[0] + p_b[0]) / 2, (p_a[1] + p_b[1]) / 2
            elif num_pontos_ciclo >= 3 : # Inclui 3 pontos para média simples, >3 para centroide
                poligono = Polygon(coords_lonlat_ciclo)
                centroide = poligono.centroid
                centro_lat, centro_lon = centroide.y, centroide.x
            else: # 1 ponto? Usa ele mesmo.
                centro_lat, centro_lon = coords_ciclo[0][0], coords_ciclo[0][1]

        except Exception as e:
            print(f"⚠️ Erro ao calcular centroide para '{nome_ciclo}', usando média: {e}")
            if not coords_ciclo: continue
            centro_lat = mean([lat for lat, lon in coords_ciclo])
            centro_lon = mean([lon for lat, lon in coords_ciclo])

        # Verifica se um pivô com nome similar ou posição próxima já existe
        distancia_min_para_match = 0.0002 # Aproximadamente 22 metros
        match_encontrado = False
        if nome_pivo_normalizado_tentativa in nomes_pivos_existentes_norm :
            match_encontrado = True
        else:
            for pivo_existente in pivos:
                dist = sqrt((pivo_existente["lat"] - centro_lat)**2 + (pivo_existente["lon"] - centro_lon)**2)
                if dist < distancia_min_para_match:
                    match_encontrado = True
                    break
        
        if not match_encontrado:
            # Garante nome único para pivô virtual se o nome derivado do círculo for muito genérico
            if not nome_base_pivo or "pivô" not in nome_virtual_pivo.lower() or len(nome_pivo_normalizado_tentativa) < 2 :
                 nome_virtual_pivo = f"Pivô Virtual {contador_virtual}"
                 contador_virtual +=1

            novos_pivos_virtuais.append({"nome": nome_virtual_pivo, "lat": centro_lat, "lon": centro_lon})
            nomes_pivos_existentes_norm.add(normalizar_nome(nome_virtual_pivo)) # Adiciona à lista para evitar duplicatas na mesma sessão de parse
            print(f"[DEBUG] Pivô Virtual Adicionado: {nome_virtual_pivo} → Lat: {centro_lat:.6f}, Lon: {centro_lon:.6f}")

    pivos.extend(novos_pivos_virtuais)
    return antena, pivos, ciclos, bombas
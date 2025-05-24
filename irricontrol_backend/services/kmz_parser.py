import os
import zipfile
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon
from math import sqrt
from typing import List, Tuple, Dict, Any, Optional
from app.utils.file_helpers import normalizar_nome
import re


AntenaDict = Dict[str, Any]
PivoDict = Dict[str, Any]
CicloDict = Dict[str, Any]
BombaDict = Dict[str, Any]


def parse_kmz(caminho_kmz: str) -> Tuple[Optional[AntenaDict], List[PivoDict], List[CicloDict], List[BombaDict]]:
    antena = None
    pivos = []
    ciclos = []
    bombas = []

    os.makedirs("arquivos", exist_ok=True)

    with zipfile.ZipFile(caminho_kmz, 'r') as kmz_file:
        for nome_arquivo_interno in kmz_file.namelist():
            if nome_arquivo_interno.endswith('.kml'):
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

                    nome_texto = (nome_element.text or "").strip()
                    nome_lower = nome_texto.lower()

                    if ponto_element is not None:
                        coords = list(map(float, ponto_element.text.strip().split(",")))
                        lon, lat = coords[0], coords[1]

                        if any(x in nome_lower for x in ["antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]):
                            altura = 15
                            altura_match = re.search(r"(\d{1,3})\s*(m|metros)", nome_lower)
                            if altura_match:
                                altura = int(altura_match.group(1))

                            antena = {"lat": lat, "lon": lon, "altura": altura, "altura_receiver": 3, "nome": nome_texto}

                        elif "pivô" in nome_lower or re.match(r"p\s?\d+", nome_lower):
                            nome_norm = normalizar_nome(nome_texto)
                            if not any(normalizar_nome(p["nome"]) == nome_norm for p in pivos):
                                pivos.append({"nome": nome_texto, "lat": lat, "lon": lon})

                        elif "casa de bomba" in nome_lower or "irripump" in nome_lower:
                            bombas.append({"nome": nome_texto, "lat": lat, "lon": lon})

                    if linha_element is not None and "medida do círculo" in nome_lower:
                        coords_list = []
                        for coord_str in linha_element.text.strip().split():
                            parts = coord_str.split(",")
                            if len(parts) >= 2:
                                coords_list.append([float(parts[1]), float(parts[0])]) # lat, lon

                        if coords_list:
                            ciclos.append({"nome": nome_texto, "coordenadas": coords_list})

                try:
                    os.remove(caminho_kml_extraido)
                    if not os.listdir(extract_path):
                        os.rmdir(extract_path)
                except Exception as e:
                    print(f"Aviso ao limpar arquivos temporários: {e}")

    # 🧠 Gera pivôs com nome automático se não tiver placemark
    nomes_existentes = {normalizar_nome(p["nome"]) for p in pivos}
    contador_pivo = 1

    for ciclo in ciclos:
        coords = ciclo["coordenadas"]
        if not coords:
            continue

        try:
            polygon = Polygon([(lon, lat) for lat, lon in coords])
            centroide = polygon.centroid
            lat_centro, lon_centro = centroide.y, centroide.x
        except Exception:
            lat_centro = mean([lat for lat, lon in coords])
            lon_centro = mean([lon for lat, lon in coords])

        nome_gerado = f"Pivô {contador_pivo:02d}"
        while normalizar_nome(nome_gerado) in nomes_existentes:
            contador_pivo += 1
            nome_gerado = f"Pivô {contador_pivo:02d}"

        pivos.append({"nome": nome_gerado, "lat": lat_centro, "lon": lon_centro})
        nomes_existentes.add(normalizar_nome(nome_gerado))
        print(f"[DEBUG] Pivô criado a partir do círculo: {nome_gerado} → ({lat_centro:.6f}, {lon_centro:.6f})")
        contador_pivo += 1

    return antena, pivos, ciclos, bombas
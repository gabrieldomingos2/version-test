from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import zipfile
import os
import xml.etree.ElementTree as ET
import httpx
import base64
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://projeto-irricontrol.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

API_URL = "https://api.cloudrf.com/area"
API_KEY = "35113-e181126d4af70994359d767890b3a4f2604eb0ef"
API_BASE_URL = "https://projeto-irricontrol.onrender.com"

def parse_kmz(caminho_kmz):
    antena = None
    pivos = []
    circulos = []

    with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
        for nome_arquivo in kmz.namelist():
            if nome_arquivo.endswith('.kml'):
                kmz.extract(nome_arquivo, "arquivos")
                caminho_kml = os.path.join("arquivos", nome_arquivo)
                tree = ET.parse(caminho_kml)
                root = tree.getroot()
                ns = {"kml": "http://www.opengis.net/kml/2.2"}

                for placemark in root.findall(".//kml:Placemark", ns):
                    nome = placemark.find("kml:name", ns)
                    ponto = placemark.find(".//kml:Point/kml:coordinates", ns)
                    linha = placemark.find(".//kml:LineString/kml:coordinates", ns)

                    if nome is not None:
                        nome_texto = nome.text.lower()

                        # Ponto da antena ou pivô
                        if ponto is not None:
                            coords = ponto.text.strip().split(",")
                            lon, lat = float(coords[0]), float(coords[1])

                            if any(p in nome_texto for p in ["antena", "torre", "barracão", "galpão", "silo", "repetidora"]):
                                match = re.search(r"(\d{1,3})\s*(m|metros)", nome.text.lower())
                                altura = int(match.group(1)) if match else 15
                                antena = {"lat": lat, "lon": lon, "altura": altura, "nome": nome.text}
                            elif "pivô" in nome_texto or "pivô" in nome.text.lower():
                                pivos.append({"nome": nome.text, "lat": lat, "lon": lon})

                        # Círculo desenhado
                        elif linha is not None and "medida do círculo" in nome_texto:
                            coords_text = linha.text.strip()
                            coordenadas = []
                            for linha_coord in coords_text.split():
                                partes = linha_coord.split(",")
                                if len(partes) >= 2:
                                    lon, lat = float(partes[0]), float(partes[1])
                                    coordenadas.append([lat, lon])
                            circulos.append({"nome": nome.text, "coordenadas": coordenadas})

    return antena, pivos, circulos

@app.post("/processar_kmz")
async def processar_kmz(file: UploadFile = File(...)):
    conteudo = await file.read()
    os.makedirs("arquivos", exist_ok=True)

    caminho_kmz = "arquivos/entrada.kmz"
    with open(caminho_kmz, "wb") as f:
        f.write(conteudo)

    antena, pivos, circulos = parse_kmz(caminho_kmz)
    if not antena:
        return {"erro": "Antena não encontrada no KMZ"}

    return {"antena": antena, "pivos": pivos, "circulos": circulos}

@app.post("/simular_sinal")
async def simular_sinal(antena: dict):
    payload = {
        "version": "CloudRF-API-v3.23",
        "site": "Brazil V6",
        "network": "My Network",
        "engine": 2,
        "coordinates": 1,
        "transmitter": {
            "lat": antena["lat"],
            "lon": antena["lon"],
            "alt": antena["altura"],
            "frq": 915,
            "txw": 0.3,
            "bwi": 0.1,
            "powerUnit": "W"
        },
        "receiver": {
            "lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -90
        },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {"mode": "template", "txg": 3, "txl": 0, "ant": 1,
                     "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "fbr": 3, "pol": "v"},
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "obstacles": 0, "clt": "Minimal.clt"},
        "output": {"units": "m", "col": "IRRICONTRO.dBm", "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10}
    }

    headers = {"key": API_KEY, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        resposta = await client.post(API_URL, headers=headers, json=payload)

    if resposta.status_code != 200:
        return {"erro": "Erro na requisição", "detalhes": resposta.text}

    data = resposta.json()
    imagem_url = data.get("PNG_WGS84")
    bounds = data.get("bounds")
    return {
        "imagem_salva": imagem_url,
        "bounds": bounds,
        "status": "Simulação concluída"
    }

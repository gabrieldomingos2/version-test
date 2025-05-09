# main.py (com /processar_kmz e /simular_sinal)

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

                    if nome is not None and ponto is not None:
                        nome_texto = nome.text.lower()
                        coords = ponto.text.strip().split(",")
                        lon, lat = float(coords[0]), float(coords[1])

                        if any(p in nome_texto for p in ["antena", "torre", "barrac\u00e3o", "galp\u00e3o", "silo", "repetidora"]):
                            match = re.search(r"(\\d+)\\s*m", nome_texto)
                            altura = int(match.group(1)) if match else 15
                            antena = {"lat": lat, "lon": lon, "altura": altura, "nome": nome.text}
                        elif "piv\u00f4" in nome_texto or "pivô" in nome.text.lower():
                            pivos.append({"nome": nome.text, "lat": lat, "lon": lon})

    return antena, pivos


@app.post("/processar_kmz")
async def processar_kmz(file: UploadFile = File(...)):
    conteudo = await file.read()
    os.makedirs("arquivos", exist_ok=True)

    caminho_kmz = "arquivos/entrada.kmz"
    with open(caminho_kmz, "wb") as f:
        f.write(conteudo)

    antena, pivos = parse_kmz(caminho_kmz)
    if not antena:
        return {"erro": "Antena n\u00e3o encontrada no KMZ"}

    return {"antena": antena, "pivos": pivos}


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
        return {"erro": "Erro na requisic\u00e3o", "detalhes": resposta.text}

    data = resposta.json()
    imagem_url = data.get("PNG_WGS84")
    bounds = data.get("bounds")
    return {
        "imagem_salva": imagem_url,
        "bounds": bounds,
        "status": "Simula\u00e7\u00e3o conclu\u00edda"
    }
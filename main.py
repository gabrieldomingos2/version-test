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

# CORS liberado para o site do Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://simulador-cloudrf-kmz.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

API_URL = "https://api.cloudrf.com/area"
API_KEY = "35113-e181126d4af70994359d767890b3a4f2604eb0ef"
API_BASE_URL = "https://simulador-cloudrf-kmz.onrender.com"

def extrair_antena_do_kmz(caminho_kmz):
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
                        if any(p in nome_texto for p in ["antena", "torre", "barracão", "galpão", "silo", "repetidora"]):
                            coords = ponto.text.strip().split(",")
                            lon, lat = float(coords[0]), float(coords[1])
                            match = re.search(r"(\d+)\s*m", nome_texto)
                            altura = int(match.group(1)) if match else 15
                            return {"lat": lat, "lon": lon, "altura": altura}
    return None

def montar_payload(antena):
    return {
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
            "lat": 0,
            "lon": 0,
            "alt": 3,
            "rxg": 3,
            "rxs": -90
        },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {
            "mode": "template", "txg": 3, "txl": 0, "ant": 1,
            "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "fbr": 3, "pol": "v"
        },
        "model": {
            "pm": 1, "pe": 2, "ked": 4, "rel": 95,
            "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100
        },
        "environment": {
            "elevation": 1, "landcover": 1,
            "buildings": 0, "obstacles": 0, "clt": "Minimal.clt"
        },
        "output": {
            "units": "m", "col": "IRRICONTRO.dBm", "out": 2,
            "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10
        }
    }

@app.post("/testar")
async def testar_envio(file: UploadFile = File(...)):
    print("📥 Recebendo arquivo KMZ...")
    conteudo = await file.read()
    os.makedirs("arquivos", exist_ok=True)
    os.makedirs("static/imagens", exist_ok=True)

    caminho_kmz = "arquivos/entrada.kmz"
    with open(caminho_kmz, "wb") as f:
        f.write(conteudo)
    print("✅ KMZ salvo.")

    antena = extrair_antena_do_kmz(caminho_kmz)
    if not antena:
        print("❌ Antena não encontrada.")
        return {"erro": "Antena não encontrada no KMZ"}
    print(f"📡 Antena detectada: {antena}")

    payload = montar_payload(antena)
    headers = {"key": API_KEY, "Content-Type": "application/json"}

    print("🔁 Enviando payload...")
    async with httpx.AsyncClient() as client:
        resposta = await client.post(API_URL, headers=headers, json=payload)

    if resposta.status_code != 200:
        print("❌ Falha na API CloudRF:", resposta.text)
        return {"erro": "Erro na requisição", "detalhes": resposta.text}

    data = resposta.json()
    print("📦 RESPOSTA COMPLETA DA API:")
    print(data)

    imagem_base64 = data.get("image", "")
    imagem_url = data.get("PNG_WGS84", "")
    kmz_data = data.get("kmz")

    caminho_imagem = "static/imagens/sinal.png"
    if imagem_base64:
        try:
            with open(caminho_imagem, "wb") as f:
                f.write(base64.b64decode(imagem_base64))
            print("✅ sinal.png salvo do base64.")
        except Exception as e:
            print("❌ Erro ao salvar PNG base64:", e)
    elif imagem_url:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(imagem_url)
                with open(caminho_imagem, "wb") as f:
                    f.write(r.content)
            print("✅ sinal.png salvo da URL.")
        except Exception as e:
            print("❌ Erro ao baixar PNG da URL:", e)
    else:
        print("⚠️ Nenhuma imagem retornada.")

    caminho_kmz_saida = "static/imagens/sinal.kmz"
    if kmz_data:
        try:
            if kmz_data.strip().startswith("http"):
                async with httpx.AsyncClient() as client:
                    r = await client.get(kmz_data)
                    with open(caminho_kmz_saida, "wb") as f:
                        f.write(r.content)
                print("✅ sinal.kmz salvo via URL.")
            else:
                with open(caminho_kmz_saida, "wb") as f:
                    f.write(base64.b64decode(kmz_data))
                print("✅ sinal.kmz salvo via base64.")
        except Exception as e:
            print("❌ Erro ao salvar KMZ:", e)
    else:
        print("⚠️ Nenhum KMZ retornado.")

    return {
        "status": "Simulação concluída",
        "altura_detectada": antena["altura"],
        "imagem_salva": f"{API_BASE_URL}/static/imagens/sinal.png",
        "kmz_salvo": f"{API_BASE_URL}/static/imagens/sinal.kmz",
        "imagem_existe": os.path.exists(caminho_imagem),
        "kmz_existe": os.path.exists(caminho_kmz_saida)
    }

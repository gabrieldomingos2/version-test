from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import zipfile, os, xml.etree.ElementTree as ET, httpx, re
from PIL import Image

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

@app.get("/icone-torre")
def icone_torre():
    return FileResponse("static/imagens/cloudrf.png", media_type="image/png")

def parse_kmz(caminho_kmz):
    antena = None
    pivos = []
    ciclos = []

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

                        if any(p in nome_texto for p in ["antena", "torre", "barracão", "galpão", "silo", "repetidora"]):
                            match = re.search(r"(\d{1,3})\s*(m|metros)", nome.text.lower())
                            altura = int(match.group(1)) if match else 15
                            antena = {"lat": lat, "lon": lon, "altura": altura, "nome": nome.text}
                        elif "pivô" in nome_texto:
                            pivos.append({"nome": nome.text, "lat": lat, "lon": lon})

                    linha = placemark.find(".//kml:LineString/kml:coordinates", ns)
                    if nome is not None and linha is not None and "medida do círculo" in nome.text.lower():
                        coords_texto = linha.text.strip().split()
                        coords = []
                        for c in coords_texto:
                            lon, lat = map(float, c.split(",")[:2])
                            coords.append([lat, lon])
                        ciclos.append({"nome": nome.text, "coordenadas": coords})

    return antena, pivos, ciclos

def detectar_pivos_fora(bounds, pivos, caminho_imagem="static/imagens/sinal.png", pivos_existentes=[]):
    
    try:
        img = Image.open(caminho_imagem).convert("RGBA")
        largura, altura = img.size

        sul, oeste, norte, leste = bounds[0], bounds[1], bounds[2], bounds[3]
        if sul > norte:
            sul, norte = norte, sul
        if oeste > leste:
            oeste, leste = leste, oeste

        resultado = []
        for pivo in pivos:
            x = int((pivo["lon"] - oeste) / (leste - oeste) * largura)
            y = int((norte - pivo["lat"]) / (norte - sul) * altura)

            if 0 <= x < largura and 0 <= y < altura:
                r, g, b, a = img.getpixel((x, y))
                dentro_cobertura = a > 0
            else:
                dentro_cobertura = False

            # Se ele já estava coberto em estudos anteriores, continua verde!
            ja_estava_coberto = any(p["nome"] == pivo["nome"] and not p.get("fora", False) for p in pivos_existentes)
            pivo["fora"] = not dentro_cobertura and not ja_estava_coberto

            resultado.append(pivo)

        return resultado

    except Exception as e:
        print("Erro na análise de imagem:", e)
        return pivos


@app.post("/processar_kmz")
async def processar_kmz(file: UploadFile = File(...)):
    conteudo = await file.read()
    os.makedirs("arquivos", exist_ok=True)
    caminho_kmz = "arquivos/entrada.kmz"
    with open(caminho_kmz, "wb") as f:
        f.write(conteudo)
    antena, pivos, ciclos = parse_kmz(caminho_kmz)
    if not antena:
        return {"erro": "Antena não encontrada no KMZ"}
    return {"antena": antena, "pivos": pivos, "ciclos": ciclos}

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
        "antenna": {
            "mode": "template", "txg": 3, "txl": 0, "ant": 1,
            "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "fbr": 3, "pol": "v"
        },
        "model": {
            "pm": 1, "pe": 2, "ked": 4, "rel": 95,
            "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100
        },
        "environment": {
            "elevation": 1, "landcover": 1, "buildings": 0,
            "obstacles": 0, "clt": "Minimal.clt"
        },
        "output": {
            "units": "m", "col": "IRRICONTRO.dBm", "out": 2,
            "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10
        }
    }

    headers = {"key": API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        resposta = await client.post(API_URL, headers=headers, json=payload)

    if resposta.status_code != 200:
        return {"erro": "Erro na requisição", "detalhes": resposta.text}

    data = resposta.json()
    imagem_url = data.get("PNG_WGS84")
    bounds = data.get("bounds")

    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open("static/imagens/sinal.png", "wb") as f:
            f.write(r.content)

    _, pivos, _ = parse_kmz("arquivos/entrada.kmz")
    pivos_com_status = detectar_pivos_fora(bounds, pivos)

    return {
        "imagem_salva": imagem_url,
        "bounds": bounds,
        "status": "Simulação concluída",
        "pivos": pivos_com_status
    }

@app.post("/simular_manual")
async def simular_manual(params: dict):
    payload = {
        "version": "CloudRF-API-v3.23",
        "site": "Manual Entry",
        "network": "Modo Expert",
        "engine": 2,
        "coordinates": 1,
        "transmitter": {
            "lat": params["lat"],
            "lon": params["lon"],
            "alt": params.get("altura", 15),
            "frq": 915,
            "txw": 0.3,
            "bwi": 0.1,
            "powerUnit": "W"
        },
        "receiver": {
            "lat": 0,
            "lon": 0,
            "alt": params.get("altura_receiver", 3),
            "rxg": 3,
            "rxs": -90
        },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {
            "mode": "template",
            "txg": 3,
            "txl": 0,
            "ant": 1,
            "azi": 0,
            "tlt": 0,
            "hbw": 360,
            "vbw": 90,
            "fbr": 3,
            "pol": "v"
        },
        "model": {
            "pm": 1,
            "pe": 2,
            "ked": 4,
            "rel": 95,
            "rcs": 1,
            "month": 4,
            "hour": 12,
            "sunspots_r12": 100
        },
        "environment": {
            "elevation": 1,
            "landcover": 1,
            "buildings": 0,
            "obstacles": 0,
            "clt": "Minimal.clt"
        },
        "output": {
            "units": "m",
            "col": "IRRICONTRO.dBm",
            "out": 2,
            "ber": 1,
            "mod": 7,
            "nf": -120,
            "res": 30,
            "rad": 10
        }
    }

    headers = {"key": API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        resposta = await client.post(API_URL, headers=headers, json=payload)

    if resposta.status_code != 200:
        return {"erro": "Erro na requisição manual", "detalhes": resposta.text}

    data = resposta.json()
    imagem_url = data.get("PNG_WGS84")
    bounds = data.get("bounds")

    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open("static/imagens/sinal_manual.png", "wb") as f:
            f.write(r.content)

    _, pivos, _ = parse_kmz("arquivos/entrada.kmz")
    pivos_atuais = params.get("pivos_atuais", [])
    pivos_com_status = detectar_pivos_fora(bounds, pivos, "static/imagens/sinal_manual.png", pivos_atuais)

    return {
        "imagem_salva": "/static/imagens/sinal_manual.png",
        "bounds": bounds,
        "status": "Simulação manual concluída",
        "pivos": pivos_com_status
    }

# ⛰️ Função: detecta os pontos mais altos da imagem (base no canal verde)
def detectar_pontos_altos(bounds, caminho_imagem="static/imagens/sinal.png", top_n=5):
    try:
        img = Image.open(caminho_imagem).convert("RGB")
        largura, altura = img.size
        sul, oeste, norte, leste = bounds

        pixels = []

        for y in range(altura):
            for x in range(largura):
                r, g, b = img.getpixel((x, y))
                score = g - r - b
                if score > 50:
                    lat = norte - (y / altura) * (norte - sul)
                    lon = oeste + (x / largura) * (leste - oeste)
                    pixels.append((score, lat, lon))

        top_pontos = sorted(pixels, key=lambda x: -x[0])[:top_n]
        return [{"lat": lat, "lon": lon, "score": score} for score, lat, lon in top_pontos]

    except Exception as e:
        print("Erro ao detectar pontos altos:", e)
        return []

# 🧪 Endpoint de diagnóstico para visualizar os pontos mais altos
@app.get("/diagnostico/pontos-altos")
async def diagnostico_pontos_altos():
    caminho_imagem = "static/imagens/sinal.png"
    bounds = [-21.9361, -47.0956, -21.7426, -46.9021]  # substitua se quiser tornar dinâmico
    pontos = detectar_pontos_altos(bounds, caminho_imagem)
    return {"pontos_altos": pontos}

    
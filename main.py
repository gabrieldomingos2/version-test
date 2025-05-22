from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import os
import zipfile
import re
import json
import httpx
import xml.etree.ElementTree as ET
import simplekml

from PIL import Image
from statistics import mean
from shapely.geometry import Polygon
from datetime import datetime
from math import sqrt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://irricontrol-test.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

API_URL = "https://api.cloudrf.com/area"
API_KEY = "35113-e181126d4af70994359d767890b3a4f2604eb0ef"

# ⏳ Timeout global para todas as requisições HTTP
HTTP_TIMEOUT = 60.0

# 🔥 Cliente HTTP com timeout global
def get_http_client():
    return httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT))


# 🔧 Função auxiliar para normalizar nomes
def normalizar_nome(nome):
    if not nome:
        return ""
    return re.sub(r'[^a-z0-9]', '', nome.lower())

# 🔧 Função padrão para formatar coordenadas em nomes de arquivos
def format_coord(coord):
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

# 🔥 Templates disponíveis no sistema
TEMPLATES_DISPONIVEIS = [
    {
        "id": "Brazil_V6",
        "nome": "🇧🇷 Brazil V6",
        "frq": 915,
        "col": "IRRICONTRO.dBm",
        "site": "Brazil_V6",
        "rxs": -90,
        "transmitter": {
            "txw": 0.3,  # Potência em watts
            "bwi": 0.1   # Largura de banda
        },
        "receiver": {
            "lat": 0,
            "lon": 0,
            "alt": 3,
            "rxg": 3,
            "rxs": -90
        },
        "antenna": {
            "txg": 3,    # Ganho da antena
            "fbr": 3     # Front-to-Back Ratio
        }
    },
    {
        "id": "Europe_V6_XR",
        "nome": "🇪🇺 Europe V6 XR",
        "frq": 868,
        "col": "IRRIEUROPE.dBm",
        "site": "V6_XR.dBm",
        "rxs": -105,
        "transmitter": {
            "txw": 0.02,
            "bwi": 0.05
        },
        "receiver": {
            "lat": 0,
            "lon": 0,
            "alt": 3,
            "rxg": 2.1,
            "rxs": -105
        },
        "antenna": {
            "txg": 2.1,
            "fbr": 2.1
        }
    }
]

# ✅ Endpoint para listar os templates disponíveis
@app.get("/templates")
def listar_templates():
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]

# ✅ Função auxiliar para obter os dados de um template
def obter_template(template_id):
    template = next((t for t in TEMPLATES_DISPONIVEIS if t["id"] == template_id), None)
    if not template:
        raise ValueError(f"Template '{template_id}' não encontrado.")
    return template


@app.get("/icone-torre")
def icone_torre():
    return FileResponse("static/imagens/cloudrf.png", media_type="image/png")


def parse_kmz(caminho_kmz):
    antena = None
    pivos = []
    ciclos = []
    bombas = []

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
                        if len(coords) < 2:
                            continue
                        lon, lat = float(coords[0]), float(coords[1])

                        # 🔗 Antena
                        if any(p in nome_texto for p in ["antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]):
                            match = re.search(r"(\d{1,3})\s*(m|metros)", nome.text.lower())
                            altura = int(match.group(1)) if match else 15
                            antena = {
                                "lat": lat,
                                "lon": lon,
                                "altura": altura,
                                "altura_receiver": 3,
                                "nome": nome.text
                            }

                        # 🎯 Pivôs
                        elif "pivô" in nome_texto or re.match(r"p\s?\d+", nome_texto):
                            nome_formatado = nome.text.strip()
                            nome_normalizado = normalizar_nome(nome_formatado)

                            if not any(normalizar_nome(p["nome"]) == nome_normalizado for p in pivos):
                                pivos.append({
                                    "nome": nome_formatado,
                                    "lat": lat,
                                    "lon": lon
                                })

                        # 🚰 Casas de bomba
                        elif "casa de bomba" in nome_texto or "irripump" in nome_texto:
                            bombas.append({
                                "nome": nome.text.strip(),
                                "lat": lat,
                                "lon": lon
                            })

                    # 🔵 Círculos desenhados
                    linha = placemark.find(".//kml:LineString/kml:coordinates", ns)
                    if nome is not None and linha is not None and "medida do círculo" in nome.text.lower():
                        coords_texto = linha.text.strip().split()
                        coords = []
                        for c in coords_texto:
                            partes = c.split(",")
                            if len(partes) >= 2:
                                lon, lat = map(float, partes[:2])
                                coords.append([lat, lon])
                        ciclos.append({
                            "nome": nome.text.strip(),
                            "coordenadas": coords
                        })

    # 🔥 Cria pivôs virtuais se não houver marcador direto no KMZ
    nomes_existentes = {normalizar_nome(p["nome"]) for p in pivos}
    contador_virtual = 1

    for ciclo in ciclos:
        nome = ciclo.get("nome", "").strip()
        coords = ciclo.get("coordenadas", [])
        if not nome or not coords:
            continue

        nome_normalizado = normalizar_nome(nome.replace("medida do círculo", ""))
        nome_virtual = f"Pivô {nome_normalizado}".strip()

        try:
            coords_lonlat = [(lon, lat) for lat, lon in coords]

            # Detecta as duas extremidades mais distantes
            max_dist = 0
            ponto_a = coords_lonlat[0]
            ponto_b = coords_lonlat[1]
            for i in range(len(coords_lonlat)):
                for j in range(i + 1, len(coords_lonlat)):
                    dist = ((coords_lonlat[i][0] - coords_lonlat[j][0]) ** 2 +
                            (coords_lonlat[i][1] - coords_lonlat[j][1]) ** 2) ** 0.5
                    if dist > max_dist:
                        max_dist = dist
                        ponto_a = coords_lonlat[i]
                        ponto_b = coords_lonlat[j]

            if max_dist > 0.001:
                centro_lon = (ponto_a[0] + ponto_b[0]) / 2
                centro_lat = (ponto_a[1] + ponto_b[1]) / 2
            else:
                poligono = Polygon(coords_lonlat)
                centroide = poligono.centroid
                centro_lat = centroide.y
                centro_lon = centroide.x

        except Exception as e:
            print("⚠️ Erro no centroide, fallback para média:", e)
            lats = [lat for lat, lon in coords]
            lons = [lon for lat, lon in coords]
            centro_lat = mean(lats)
            centro_lon = mean(lons)

        distancia_minima = 0.0002
        existe_placemark = any(
            normalizar_nome(p["nome"]) == nome_normalizado or
            sqrt((p["lat"] - centro_lat) ** 2 + (p["lon"] - centro_lon) ** 2) < distancia_minima
            for p in pivos
        )

        if existe_placemark:
            continue

        if not re.search(r"\d+", nome_virtual):
            nome_virtual = f"Pivô {contador_virtual}"
            contador_virtual += 1

        pivos.append({
            "nome": nome_virtual,
            "lat": centro_lat,
            "lon": centro_lon
        })

        print(f"[DEBUG] {nome_virtual} → Lat: {centro_lat:.6f}, Lon: {centro_lon:.6f}")

    return antena, pivos, ciclos, bombas

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
    try:
        print("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()

        os.makedirs("arquivos", exist_ok=True)
        caminho_kmz = "arquivos/entrada.kmz"

        with open(caminho_kmz, "wb") as f:
            f.write(conteudo)

        print("📦 KMZ salvo em:", caminho_kmz)

        # LOGA conteúdo do ZIP
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            print("🗂️ Conteúdo do KMZ:", kmz.namelist())

        antena, pivos, ciclos, bombas = parse_kmz(caminho_kmz)

        if not antena:
            return {"erro": "Antena não encontrada no KMZ"}

        if ciclos:
            maior = max(ciclos, key=lambda c: len(c["coordenadas"]))
            coords_fazenda = [[lon, lat] for lat, lon in maior["coordenadas"]]
            with open("static/contorno_fazenda.json", "w") as f:
                json.dump(coords_fazenda, f)

        return {
            "antena": antena,
            "pivos": pivos,
            "ciclos": ciclos,
            "bombas": bombas
        }

    except Exception as e:
        print("❌ Erro em /processar_kmz:", str(e))
        return {"erro": f"Erro interno ao processar KMZ: {str(e)}"}


@app.post("/simular_sinal")
async def simular_sinal(antena: dict):
    print("📡 Antena recebida:", antena)

    if not antena or not all(k in antena for k in ("lat", "lon", "altura", "template")):
        return {"erro": "Dados incompletos para simulação", "antena": antena}

    try:
        tpl = obter_template(antena["template"])
    except ValueError as e:
        return {"erro": str(e)}

    # 🔥 Remove arquivos antigos de sinal da torre
    for arquivo in os.listdir("static/imagens"):
        if arquivo.startswith("sinal_"):
            os.remove(os.path.join("static/imagens", arquivo))

    pivos_recebidos = antena.get("pivos_atuais", [])

    payload = {
        "version": "CloudRF-API-v3.24",
        "site": tpl["site"],
        "network": "Network",
        "engine": 2,
        "coordinates": 1,
        "transmitter": {
            "lat": antena["lat"],
            "lon": antena["lon"],
            "alt": antena["altura"],
            "frq": tpl["frq"],
            "txw": tpl["transmitter"]["txw"],
            "bwi": tpl["transmitter"]["bwi"],
            "powerUnit": "W"
        },
        "receiver": {
            "lat": tpl["receiver"]["lat"],
            "lon": tpl["receiver"]["lon"],
            "alt": tpl["receiver"]["alt"],
            "rxg": tpl["receiver"]["rxg"],
            "rxs": tpl["receiver"]["rxs"]
        },
        "feeder": {
            "flt": 1,
            "fll": 0,
            "fcc": 0
        },
        "antenna": {
            "mode": "template",
            "txg": tpl["antenna"]["txg"],
            "txl": 0,
            "ant": 1,
            "azi": 0,
            "tlt": 0,
            "hbw": 360,
            "vbw": 90,
            "fbr": tpl["antenna"]["fbr"],
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
            "col": tpl["col"],
            "out": 2,
            "ber": 1,
            "mod": 7,
            "nf": -120,
            "res": 30,
            "rad": 10
        }
    }

    print("🚀 Payload enviado:", json.dumps(payload, indent=2))

    headers = {"key": API_KEY, "Content-Type": "application/json"}
    timeout = httpx.Timeout(60.0)  # 🔥 60 segundos
    async with httpx.AsyncClient() as client:
        resposta = await client.post(API_URL, headers=headers, json=payload)

    if resposta.status_code != 200:
        return {"erro": "Erro na requisição", "detalhes": resposta.text}

    data = resposta.json()
    imagem_url = data.get("PNG_WGS84")
    bounds = data.get("bounds")

    if not imagem_url or not bounds:
        return {"erro": "Resposta inválida da API CloudRF", "dados": data}

    # 🔥 Nomes dos arquivos com base no template e coordenadas
    lat_str = format_coord(antena["lat"])
    lon_str = format_coord(antena["lon"])
    nome_arquivo = f"sinal_{tpl['id'].lower()}_{lat_str}_{lon_str}.png"
    caminho_local = f"static/imagens/{nome_arquivo}"

    # 🔥 Salva imagem PNG
    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open(caminho_local, "wb") as f:
            f.write(r.content)

    # 🔥 Salva bounds em JSON separado
    json_bounds_path = caminho_local.replace(".png", ".json")
    with open(json_bounds_path, "w") as f:
        json.dump({"bounds": bounds}, f)

    # 🔎 Detecta pivôs fora da cobertura
    pivos_com_status = detectar_pivos_fora(bounds, pivos_recebidos, caminho_imagem=caminho_local)

    return {
        "imagem_salva": f"https://irricontrol-test.onrender.com/static/imagens/{nome_arquivo}",
        "bounds": bounds,
        "status": "Simulação concluída",
        "pivos": pivos_com_status
    }


@app.post("/simular_manual")
async def simular_manual(params: dict):
    print("🚀 Dados recebidos em /simular_manual:", params)

    if not all(k in params for k in ("lat", "lon", "template", "pivos_atuais")):
        return {"erro": "Dados incompletos recebidos para simulação manual", "dados": params}

    try:
        tpl = obter_template(params["template"])
    except ValueError as e:
        return {"erro": str(e)}

    # 🔥 Remove arquivos antigos de repetidoras
    for arquivo in os.listdir("static/imagens"):
        if arquivo.startswith("repetidora_"):
            os.remove(os.path.join("static/imagens", arquivo))

    payload = {
        "version": "CloudRF-API-v3.24",
        "site": tpl["site"],
        "network": "Modo Expert",
        "engine": 2,
        "coordinates": 1,
        "transmitter": {
            "lat": params["lat"],
            "lon": params["lon"],
            "alt": params.get("altura", 15),
            "frq": tpl["frq"],
            "txw": tpl["transmitter"]["txw"],
            "bwi": tpl["transmitter"]["bwi"],
            "powerUnit": "W"
        },
        "receiver": {
            "lat": tpl["receiver"]["lat"],
            "lon": tpl["receiver"]["lon"],
            "alt": tpl["receiver"]["alt"],
            "rxg": tpl["receiver"]["rxg"],
            "rxs": tpl["receiver"]["rxs"]
        },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {
            "mode": "template",
            "txg": tpl["antenna"]["txg"],
            "txl": 0,
            "ant": 1,
            "azi": 0,
            "tlt": 0,
            "hbw": 360,
            "vbw": 90,
            "fbr": tpl["antenna"]["fbr"],
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
            "col": tpl["col"],
            "out": 2,
            "ber": 1,
            "mod": 7,
            "nf": -120,
            "res": 30,
            "rad": 10
        }
    }

    print("🚀 Payload enviado (manual):", json.dumps(payload, indent=2))

    headers = {"key": API_KEY, "Content-Type": "application/json"}
    timeout = httpx.Timeout(HTTP_TIMEOUT)

    # 🔥 Faz requisição POST para gerar o sinal
    async with get_http_client() as client:
        resposta = await client.post(API_URL, headers=headers, json=payload)

    if resposta.status_code != 200:
        return {"erro": "Erro na requisição manual", "detalhes": resposta.text}

    data = resposta.json()
    imagem_url = data.get("PNG_WGS84")
    bounds = data.get("bounds")

    if not imagem_url or not bounds:
        return {"erro": "Resposta inválida da API CloudRF", "dados": data}

    # 🔥 Gera nome do arquivo com template + coordenadas
    lat_str = format_coord(params["lat"])
    lon_str = format_coord(params["lon"])
    nome_arquivo = f"repetidora_{tpl['id'].lower()}_{lat_str}_{lon_str}.png"
    caminho_local = f"static/imagens/{nome_arquivo}"

    # 🔥 Faz download da imagem PNG do sinal
    async with get_http_client() as client:
        r = await client.get(imagem_url)
        with open(caminho_local, "wb") as f:
            f.write(r.content)

    # 🔥 Salva bounds JSON
    json_bounds_path = caminho_local.replace(".png", ".json")
    with open(json_bounds_path, "w") as f:
        json.dump({"bounds": bounds}, f)

    imagem_local_url = f"https://irricontrol-test.onrender.com/static/imagens/{nome_arquivo}"

    # 🔎 Avalia cobertura dos pivôs
    pivos_recebidos = params.get("pivos_atuais", [])
    pivos_com_status = detectar_pivos_fora(
        bounds,
        pivos_recebidos,
        caminho_imagem=caminho_local,
        pivos_existentes=pivos_recebidos
    )

    return {
        "imagem_salva": imagem_local_url,
        "bounds": bounds,
        "pivos": pivos_com_status
    }

@app.post("/reavaliar_pivos")
async def reavaliar_pivos(data: dict):
    try:
        pivos = data.get("pivos", [])
        overlays = data.get("overlays", [])

        atualizados = []

        for pivo in pivos:
            lat, lon = pivo["lat"], pivo["lon"]
            coberto = False

            for overlay in overlays:
                bounds = overlay["bounds"]  # [sul, oeste, norte, leste]
                imagem_path = overlay["imagem"]

                # ✅ Corrige se veio como URL
                if imagem_path.startswith("http"):
                    imagem_path = imagem_path.replace("https://irricontrol-test.onrender.com/", "")

                try:
                    img = Image.open(imagem_path).convert("RGBA")
                    largura, altura = img.size

                    sul, oeste, norte, leste = bounds
                    if sul > norte:
                        sul, norte = norte, sul
                    if oeste > leste:
                        oeste, leste = leste, oeste

                    x = int((lon - oeste) / (leste - oeste) * largura)
                    y = int((norte - lat) / (norte - sul) * altura)

                    if 0 <= x < largura and 0 <= y < altura:
                        _, _, _, a = img.getpixel((x, y))
                        if a > 0:
                            coberto = True
                            break
                except Exception as e:
                    print(f"Erro ao analisar overlay: {imagem_path}", e)

            pivo["fora"] = not coberto
            atualizados.append(pivo)

        return {"pivos": atualizados}

    except Exception as e:
        return {"erro": f"Falha ao reavaliar pivôs: {str(e)}"}


from math import sqrt

@app.post("/perfil_elevacao")
async def perfil_elevacao(req: dict):
    pontos = req.get("pontos", [])
    alt1 = req.get("altura_antena", 15)
    alt2 = req.get("altura_receiver", 3)

    if len(pontos) < 2:
        return {"erro": "Informe pelo menos dois pontos"}

    steps = 50
    amostrados = [
        (
            pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / steps,
            pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / steps
        )
        for i in range(steps + 1)
    ]

    coords_param = "|".join([f"{lat},{lon}" for lat, lon in amostrados])
    url = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

    timeout = httpx.Timeout(HTTP_TIMEOUT)

    async with get_http_client() as client:
        resp = await client.get(url)

    dados = resp.json()
    elevs = [r["elevation"] for r in dados["results"]]

    # ⛰️ Calcula linha de visada entre antena e receiver
    elev1 = elevs[0] + alt1
    elev2 = elevs[-1] + alt2
    linha_visada = [
        elev1 + i * (elev2 - elev1) / steps
        for i in range(steps + 1)
    ]

    # 🔎 Detecta o ponto de maior elevação acima da linha de visada
    max_altura = -1
    bloqueio_real = None
    idx_max = 1

    for i in range(1, steps):
        elev = elevs[i]
        visada = linha_visada[i]

        if elev > visada and elev > max_altura:
            max_altura = elev
            bloqueio_real = {
                "lat": amostrados[i][0],
                "lon": amostrados[i][1],
                "elev": elev
            }

        if elev > elevs[idx_max]:
            idx_max = i

    bloqueio = bloqueio_real or {
        "lat": amostrados[idx_max][0],
        "lon": amostrados[idx_max][1],
        "elev": elevs[idx_max]
    }

    return {"bloqueio": bloqueio, "elevacao": elevs}

from fastapi import Query

@app.get("/exportar_kmz")
def exportar_kmz(
    imagem: str = Query(None, description="Nome da imagem PNG principal, ex: sinal_brazil_v6_-22_4756_-46_9089.png"),
    bounds_file: str = Query(None, description="Nome do JSON de bounds, ex: sinal_brazil_v6_-22_4756_-46_9089.json")
):
    try:
        antena, pivos, ciclos, _ = parse_kmz("arquivos/entrada.kmz")

        caminho_imagem = f"static/imagens/{imagem}" if imagem else None
        caminho_bounds = f"static/imagens/{bounds_file}" if bounds_file else None

        if caminho_imagem and not os.path.exists(caminho_imagem):
            return {"erro": f"Imagem {imagem} não encontrada. Rode a simulação primeiro."}

        if caminho_bounds and not os.path.exists(caminho_bounds):
             return {"erro": f"Arquivo de bounds {bounds_file} não encontrado. Rode a simulação primeiro."}


        bounds = None
        if caminho_bounds and os.path.exists(caminho_bounds):
            with open(caminho_bounds, "r") as f:
                bounds_json = json.load(f)
                bounds = bounds_json.get("bounds", bounds_json)

        if not antena or not pivos:
            return {"erro": "Antena ou pivôs não encontrados no KMZ"}

        kml = simplekml.Kml()

        # 🗼 Torre principal
        torre = kml.newpoint(name=antena["nome"], coords=[(antena["lon"], antena["lat"])])
        torre.description = f"Torre principal\nAltura: {antena['altura']}m"
        torre.style.iconstyle.icon.href = "cloudrf.png"
        torre.style.iconstyle.scale = 1.5

        # 🎯 Pivôs
        for p in pivos:
            ponto = kml.newpoint(name=p["nome"], coords=[(p["lon"], p["lat"])])
            ponto.description = "❌ Fora da cobertura" if p.get("fora") else "✅ Coberto"
            ponto.style.iconstyle.color = "ffffffff"
            ponto.style.iconstyle.scale = 1.4

        # 🔵 Círculos dos pivôs
        for ciclo in ciclos:
            poligono = kml.newpolygon(name=ciclo["nome"])
            poligono.outerboundaryis = [(lon, lat) for lat, lon in ciclo["coordenadas"]]
            poligono.style.polystyle.color = "00000000"
            poligono.style.linestyle.color = "ff0000ff"
            poligono.style.linestyle.width = 4.0

        # 🗺️ Overlay da torre principal, se existir
        if caminho_imagem and bounds and os.path.exists(caminho_imagem):
            ground = kml.newgroundoverlay(name="Cobertura Principal")
            ground.icon.href = imagem
            ground.latlonbox.north = bounds[2]
            ground.latlonbox.south = bounds[0]
            ground.latlonbox.east = bounds[3]
            ground.latlonbox.west = bounds[1]
            ground.color = "88ffffff"

        # 🔥 Adiciona overlays das repetidoras
        arquivos_overlay = os.listdir("static/imagens")
        repetidoras_adicionadas = []

        for nome_arquivo in arquivos_overlay:
            if nome_arquivo.startswith("repetidora_") and nome_arquivo.endswith(".png"):
                caminho_rep_imagem = os.path.join("static/imagens", nome_arquivo)
                caminho_rep_json = caminho_rep_imagem.replace(".png", ".json")

                if not os.path.exists(caminho_rep_json):
                    print(f"⚠️ JSON de bounds não encontrado para {nome_arquivo}")
                    continue

                try:
                    with open(caminho_rep_json, "r") as f:
                        bounds_rep = json.load(f).get("bounds", json.load(f))
                except Exception as e:
                    print(f"⚠️ Erro ao ler bounds de {nome_arquivo}: {e}")
                    continue

                overlay = kml.newgroundoverlay(name=f"Overlay {nome_arquivo}")
                overlay.icon.href = nome_arquivo
                overlay.latlonbox.south = bounds_rep[0]
                overlay.latlonbox.west = bounds_rep[1]
                overlay.latlonbox.north = bounds_rep[2]
                overlay.latlonbox.east = bounds_rep[3]
                overlay.color = "77ffffff"

                lat_centro = (bounds_rep[0] + bounds_rep[2]) / 2
                lon_centro = (bounds_rep[1] + bounds_rep[3]) / 2

                ponto = kml.newpoint(name="Repetidora", coords=[(lon_centro, lat_centro)])
                ponto.description = f"Repetidora em {lat_centro:.5f}, {lon_centro:.5f}"
                ponto.style.iconstyle.icon.href = "cloudrf.png"
                ponto.style.iconstyle.scale = 1.2

                repetidoras_adicionadas.append((caminho_rep_imagem, nome_arquivo))
                repetidoras_adicionadas.append((caminho_rep_json, nome_arquivo.replace(".png", ".json")))

        # 📦 Monta o arquivo KMZ
        caminho_kml = "arquivos/estudo.kml"
        kml.save(caminho_kml)

        nome_kmz = f"estudo-irricontrol-{datetime.now().strftime('%Y%m%d-%H%M')}.kmz"
        caminho_kmz_zip = f"arquivos/{nome_kmz}"

        with zipfile.ZipFile(caminho_kmz_zip, "w") as kmz:
            kmz.write(caminho_kml, "estudo.kml")
            if caminho_imagem and os.path.exists(caminho_imagem):
                kmz.write(caminho_imagem, imagem)
            kmz.write("static/imagens/cloudrf.png", "cloudrf.png")

            for arquivo, nome_destino in repetidoras_adicionadas:
                kmz.write(arquivo, nome_destino)

        return FileResponse(
            caminho_kmz_zip,
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz
        )

    except Exception as e:
        return {"erro": f"Erro ao exportar KMZ: {str(e)}"}
    

@app.get("/arquivos_imagens")
def listar_arquivos_imagens():
    try:
        arquivos = os.listdir("static/imagens")
        pngs = [arq for arq in arquivos if arq.endswith(".png")]
        jsons = [arq for arq in arquivos if arq.endswith(".json")]
        return {"pngs": pngs, "jsons": jsons}
    except Exception as e:
        return {"erro": str(e)}
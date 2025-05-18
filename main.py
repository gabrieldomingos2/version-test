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

                        elif "pivô" in nome_texto or re.match(r"p\s?\d+", nome_texto):
                            nome_bruto = nome.text.strip()
                            match = re.match(r"p\s?(\d+)", nome_bruto.lower())
                            if match:
                                numero = match.group(1)
                                nome_formatado = f"Pivô {numero}"
                            else:
                                nome_formatado = nome_bruto

                            pivos.append({
                                "nome": nome_formatado,
                                "lat": lat,
                                "lon": lon
                            })

                        elif "casa de bomba" in nome_texto or "irripump" in nome_texto:
                            bombas.append({
                                "nome": nome.text.strip(),
                                "lat": lat,
                                "lon": lon
                            })

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

    nomes_existentes = {p["nome"].strip().lower() for p in pivos}
    contador_virtual = 1

    for ciclo in ciclos:
        nome = ciclo.get("nome", "").strip()
        coords = ciclo.get("coordenadas", [])
        if not nome or not coords:
            continue

        nome_normalizado = nome.lower().replace("medida do círculo", "").strip()
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

            if max_dist > 0.001:  # se distância A-B for significativa
                centro_lon = (ponto_a[0] + ponto_b[0]) / 2
                centro_lat = (ponto_a[1] + ponto_b[1]) / 2
            else:
                poligono = Polygon(coords_lonlat)
                centroide = poligono.centroid
                centro_lat = centroide.y
                centro_lon = centroide.x

        except Exception as e:
            print("⚠️ Erro ao calcular centroide, usando média como fallback:", e)
            lats = [lat for lat, lon in coords]
            lons = [lon for lat, lon in coords]
            centro_lat = mean(lats)
            centro_lon = mean(lons)

        distancia_minima = 0.0002
        nome_esperado = nome_virtual.lower()
        existe_placemark = any(
            p["nome"].strip().lower() == nome_esperado or
            ((p["lat"] - centro_lat) ** 2 + (p["lon"] - centro_lon) ** 2) ** 0.5 < distancia_minima
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


import json  # garante que esteja no topo

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

    if not antena or not all(k in antena for k in ("lat", "lon", "altura")):
        return {"erro": "Dados incompletos para simulação. Antena:", "antena": antena}

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

    caminho_local = "static/imagens/sinal.png"

    # Baixa e salva a imagem
    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open(caminho_local, "wb") as f:
            f.write(r.content)

    # 🧭 Salva os bounds da antena principal
    with open("static/imagens/sinal_bounds.json", "w") as f:
        json.dump(bounds, f)

    # Reprocessa os pivôs
    _, pivos, _, _ = parse_kmz("arquivos/entrada.kmz")
    pivos_com_status = detectar_pivos_fora(bounds, pivos)

    return {
        "imagem_salva": "https://irricontrol-test.onrender.com/static/imagens/sinal.png",
        "bounds": bounds,
        "status": "Simulação concluída",
        "pivos": pivos_com_status
    }


@app.post("/simular_manual")
async def simular_manual(params: dict):
    print("🚀 Dados recebidos em /simular_manual:", params)

    if not all(k in params for k in ("lat", "lon", "pivos_atuais")):
        return {"erro": "Dados incompletos recebidos para simulação manual", "dados": params}

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

    if not imagem_url or not bounds:
        return {"erro": "Resposta inválida da API CloudRF", "dados": data}

    # 🔽 Corrige nome seguro do arquivo
    lat_str = f"{params['lat']:.5f}".replace(".", "_")
    lon_str = f"{params['lon']:.5f}".replace(".", "_")
    nome_arquivo = f"repetidora_{lat_str}_{lon_str}.png"
    caminho_local = f"static/imagens/{nome_arquivo}"

    # ⬇️ Baixa e salva a imagem da repetidora
    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open(caminho_local, "wb") as f:
            f.write(r.content)

    # 🧭 Salva os bounds em um arquivo JSON junto da imagem
    json_bounds_path = caminho_local.replace(".png", ".json")
    with open(json_bounds_path, "w") as f:
        json.dump({"bounds": bounds}, f)

    imagem_local_url = f"https://irricontrol-test.onrender.com/static/imagens/{nome_arquivo}"

    # Recarrega os pivôs
    _, pivos_atualizados, _, _ = parse_kmz("arquivos/entrada.kmz")
    pivos_anteriores = params.get("pivos_atuais", [])
    
    pivos_com_status = detectar_pivos_fora(
        bounds,
        pivos_atualizados,
        caminho_imagem=caminho_local,
        pivos_existentes=pivos_anteriores
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

    async with httpx.AsyncClient() as client:
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
    idx_max = 1  # começa do segundo ponto pra evitar sobrepor antena

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

    # Se houver um bloqueio real, use ele; senão, mostra o ponto mais alto como fallback visual
    bloqueio = bloqueio_real or {
        "lat": amostrados[idx_max][0],
        "lon": amostrados[idx_max][1],
        "elev": elevs[idx_max]
    }

    return {"bloqueio": bloqueio, "elevacao": elevs}

@app.post("/sugerir_repetidora_entre_pivos")
async def sugerir_repetidora_entre_pivos(data: dict):
    p1 = data.get("pivo1")
    p2 = data.get("pivo2")

    # MODO NORMAL ENTRE DOIS PIVÔS
    if p1 and p2:
        steps = 50
        pontos = [
            (
                p1["lat"] + (p2["lat"] - p1["lat"]) * i / steps,
                p1["lon"] + (p2["lon"] - p1["lon"]) * i / steps
            )
            for i in range(steps + 1)
        ]

        coords_param = "|".join([f"{lat},{lon}" for lat, lon in pontos])
        url = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()

            elevs = [r["elevation"] for r in resp.json()["results"]]
            idx_max = max(range(len(elevs)), key=lambda i: elevs[i])
            lat, lon, elev = pontos[idx_max][0], pontos[idx_max][1], elevs[idx_max]

            return {"sugestao": {"lat": lat, "lon": lon, "elev": elev}}

        except Exception as e:
            return {"erro": f"Erro ao consultar elevação: {str(e)}"}

    # MODO AUTOMÁTICO - TODOS FORA DA COBERTURA
    pivos = data.get("pivos")
    overlays = data.get("overlays")

    if not pivos or not overlays:
        return {"erro": "Dados insuficientes: forneça pivos e overlays se não usar pivo1/pivo2"}

    # Função para checar se ponto está coberto
    def esta_coberto(lat, lon):
        for overlay in overlays:
            s, w, n, e = overlay["bounds"]
            if s <= lat <= n and w <= lon <= e:
                return True
        return False

    # Filtra os pivôs fora da cobertura
    pivos_fora = [p for p in pivos if not esta_coberto(p["lat"], p["lon"])]

    if len(pivos_fora) < 2:
        return {"erro": "É necessário ao menos 2 pivôs fora da cobertura"}

    # Testa todos os pares únicos entre pivôs fora
    melhores = []

    for i in range(len(pivos_fora)):
        for j in range(i + 1, len(pivos_fora)):
            a = pivos_fora[i]
            b = pivos_fora[j]

            steps = 50
            pontos = [
                (
                    a["lat"] + (b["lat"] - a["lat"]) * k / steps,
                    a["lon"] + (b["lon"] - a["lon"]) * k / steps
                )
                for k in range(steps + 1)
            ]

            coords_param = "|".join([f"{lat},{lon}" for lat, lon in pontos])
            url = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url)
                    resp.raise_for_status()

                elevs = [r["elevation"] for r in resp.json()["results"]]
                idx_max = max(range(len(elevs)), key=lambda k: elevs[k])

                lat, lon, elev = pontos[idx_max][0], pontos[idx_max][1], elevs[idx_max]
                melhores.append({
                    "lat": lat,
                    "lon": lon,
                    "elev": elev,
                    "pivo1": a["nome"],
                    "pivo2": b["nome"]
                })

            except Exception as e:
                continue

    # Ordena por maior elevação
    melhores.sort(key=lambda x: -x["elev"])

    return {"sugestoes": melhores[:3]}  # top 3 sugestões


@app.get("/exportar_kmz")
def exportar_kmz():
    try:
        antena, pivos, ciclos, _ = parse_kmz("arquivos/entrada.kmz")
        caminho_imagem = "static/imagens/sinal.png"
        caminho_bounds = "static/imagens/sinal_bounds.json"

        if not antena or not pivos or not os.path.exists(caminho_imagem) or not os.path.exists(caminho_bounds):
            return {"erro": "Dados insuficientes para exportar"}

        with open(caminho_bounds, "r") as f:
            bounds = list(map(float, json.load(f)))

        kml = simplekml.Kml()

        # Torre principal
        torre = kml.newpoint(name=f"{antena['nome']}", coords=[(antena["lon"], antena["lat"])])
        torre.description = f"Torre principal\nAltura: {antena['altura']}m"
        torre.style.iconstyle.icon.href = "cloudrf.png"
        torre.style.iconstyle.scale = 1.5

        # Pivôs
        for p in pivos:
            ponto = kml.newpoint(name=p["nome"], coords=[(p["lon"], p["lat"])])
            ponto.description = "❌ Fora da cobertura" if p.get("fora") else "✅ Coberto"
            ponto.style.iconstyle.color = "ffffffff"
            ponto.style.iconstyle.scale = 1.4


        # Círculos dos pivôs
        for ciclo in ciclos:
           poligono = kml.newpolygon(name=ciclo["nome"])
           poligono.outerboundaryis = [(lon, lat) for lat, lon in ciclo["coordenadas"]]
           poligono.style.polystyle.color = "00000000" 
           poligono.style.linestyle.color = "ff0000ff" 
           poligono.style.linestyle.width = 4.0       


        # Imagem da antena principal
        ground = kml.newgroundoverlay(name="Cobertura Principal")
        ground.icon.href = "sinal.png"
        ground.latlonbox.north = bounds[2]
        ground.latlonbox.south = bounds[0]
        ground.latlonbox.east = bounds[3]
        ground.latlonbox.west = bounds[1]
        ground.color = "88ffffff"

        # Repetidoras com overlay
        repetidoras_adicionadas = []
        for nome_arquivo in os.listdir("static/imagens"):
            if nome_arquivo.startswith("repetidora_") and nome_arquivo.endswith(".png"):
                caminho = os.path.join("static/imagens", nome_arquivo)
                json_path = caminho.replace(".png", ".json")

                if not os.path.exists(json_path):
                    print(f"⚠️ JSON com bounds não encontrado para {nome_arquivo}")
                    continue

                try:
                    with open(json_path, "r") as f:
                        bounds_rep = json.load(f)["bounds"]
                except Exception as e:
                    print(f"⚠️ Erro ao carregar bounds do JSON: {json_path} → {e}")
                    continue

                nome_limpo = nome_arquivo

                overlay = kml.newgroundoverlay(name=f"Repetidora {nome_arquivo.replace('.png','')}")
                overlay.icon.href = nome_limpo
                overlay.latlonbox.south = bounds_rep[0]
                overlay.latlonbox.west = bounds_rep[1]
                overlay.latlonbox.north = bounds_rep[2]
                overlay.latlonbox.east = bounds_rep[3]
                overlay.color = "77ffffff"

                # Marca de posição da repetidora
                lat_centro = (bounds_rep[0] + bounds_rep[2]) / 2
                lon_centro = (bounds_rep[1] + bounds_rep[3]) / 2

                ponto = kml.newpoint(name="Repetidora", coords=[(lon_centro, lat_centro)])
                ponto.style.iconstyle.icon.href = "cloudrf.png"
                ponto.style.iconstyle.scale = 1.2
                ponto.description = f"Repetidora centralizada em {lat_centro:.4f}, {lon_centro:.4f}"

                repetidoras_adicionadas.append((caminho, nome_limpo))
                repetidoras_adicionadas.append((json_path, nome_limpo.replace(".png", ".json")))

        # Exporta o KML e empacota tudo como KMZ.
        caminho_kml = "arquivos/estudo.kml"
        kml.save(caminho_kml)

        nome_kmz = f"estudo-irricontrol-{datetime.now().strftime('%Y%m%d-%H%M')}.kmz"
        caminho_kmz_zip = f"arquivos/{nome_kmz}"

        with zipfile.ZipFile(caminho_kmz_zip, "w") as kmz:
            kmz.write(caminho_kml, "estudo.kml")
            kmz.write(caminho_imagem, "sinal.png")
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
    
    @app.post("/sugerir_repetidoras_automaticas")
async def sugerir_repetidoras_automaticas(data: dict):
    pivos = data.get("pivos", [])
    overlays = data.get("overlays", [])

    if not pivos or not overlays:
        return {"erro": "Dados insuficientes para sugestão automática"}

    def esta_coberto(lat, lon):
        for o in overlays:
            s, w, n, e = o["bounds"]
            if s <= lat <= n and w <= lon <= e:
                return True
        return False

    pivos_fora = [p for p in pivos if not esta_coberto(p["lat"], p["lon"])]

    if len(pivos_fora) < 2:
        return {"erro": "É necessário ao menos 2 pivôs fora da cobertura"}

    sugestoes = []
    steps = 50

    for i in range(len(pivos_fora)):
        for j in range(i + 1, len(pivos_fora)):
            p1 = pivos_fora[i]
            p2 = pivos_fora[j]

            pontos = [
                (
                    p1["lat"] + (p2["lat"] - p1["lat"]) * k / steps,
                    p1["lon"] + (p2["lon"] - p1["lon"]) * k / steps
                )
                for k in range(steps + 1)
            ]

            coords_param = "|".join([f"{lat},{lon}" for lat, lon in pontos])
            url = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url)
                    resp.raise_for_status()

                elevs = [r["elevation"] for r in resp.json()["results"]]
                idx_max = max(range(len(elevs)), key=lambda i: elevs[i])
                lat, lon, elev = pontos[idx_max][0], pontos[idx_max][1], elevs[idx_max]

                sugestoes.append({
                    "lat": lat,
                    "lon": lon,
                    "elev": elev,
                    "pivo1": p1["nome"],
                    "pivo2": p2["nome"]
                })

            except Exception as e:
                print(f"Erro ao sugerir entre {p1['nome']} e {p2['nome']}: {e}")
                continue

    return {"sugestoes": sugestoes[:3]}

    

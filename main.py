from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import zipfile, os, xml.etree.ElementTree as ET, httpx, re, json
from PIL import Image
from statistics import mean
import itertools
import numpy as np
from shapely.geometry import Point, Polygon
from math import sqrt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://version-test.netlify.app"],
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
                            antena = {"lat": lat, "lon": lon, "altura": altura, "altura_receiver": 3, "nome": nome.text}
                        elif "pivô" in nome_texto:
                            pivos.append({"nome": nome.text.strip(), "lat": lat, "lon": lon})
                        elif "casa de bomba" in nome_texto or "irripump" in nome_texto:
                            bombas.append({"nome": nome.text.strip(), "lat": lat, "lon": lon})

                    linha = placemark.find(".//kml:LineString/kml:coordinates", ns)
                    if nome is not None and linha is not None and "medida do círculo" in nome.text.lower():
                        coords_texto = linha.text.strip().split()
                        coords = []
                        for c in coords_texto:
                            partes = c.split(",")
                            if len(partes) >= 2:
                                lon, lat = map(float, partes[:2])
                                coords.append([lat, lon])
                        ciclos.append({"nome": nome.text.strip(), "coordenadas": coords})

    nomes_existentes = {p["nome"].strip().lower() for p in pivos}
    contador_virtual = 1

    for ciclo in ciclos:
        nome = ciclo.get("nome", "").strip()
        coords = ciclo.get("coordenadas", [])
        if not nome or not coords:
            continue

        nome_normalizado = nome.lower().replace("medida do círculo", "").strip()
        nome_virtual = f"Pivô {nome_normalizado}".strip()

        if nome_virtual.lower() in nomes_existentes:
            continue

        max_dist = 0
        ponto_a = coords[0]
        ponto_b = coords[1] if len(coords) > 1 else coords[0]

        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                lat1, lon1 = coords[i][:2]
                lat2, lon2 = coords[j][:2]
                dist = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
                if dist > max_dist:
                    max_dist = dist
                    ponto_a = coords[i][:2]
                    ponto_b = coords[j][:2]

        if max_dist > 0.0005:
            centro_lat = (ponto_a[0] + ponto_b[0]) / 2
            centro_lon = (ponto_a[1] + ponto_b[1]) / 2
        else:
            lats = [lat for lat, lon in coords]
            lons = [lon for lat, lon in coords]
            centro_lat = mean(lats)
            centro_lon = mean(lons)

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

    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open("static/imagens/sinal.png", "wb") as f:
            f.write(r.content)

    _, pivos, _, _ = parse_kmz("arquivos/entrada.kmz")
    pivos_com_status = detectar_pivos_fora(bounds, pivos)

    return {
        "imagem_salva": "https://version-test.onrender.com/static/imagens/sinal.png",
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

    # 🔽 Corrige nome do arquivo com extensão e nome seguro
    lat_str = str(params["lat"]).replace(".", "_")
    lon_str = str(params["lon"]).replace(".", "_")
    nome_arquivo = f"repetidora_{lat_str}_{lon_str}.png"
    caminho_local = f"static/imagens/{nome_arquivo}"

    async with httpx.AsyncClient() as client:
        r = await client.get(imagem_url)
        with open(caminho_local, "wb") as f:
            f.write(r.content)

        # 🔁 URL final acessível via frontend (Netlify)
    imagem_local_url = f"https://version-test.onrender.com/static/imagens/{nome_arquivo}"

    # Recarrega os pivôs reais do KMZ
    _, pivos_atualizados, _, _ = parse_kmz("arquivos/entrada.kmz")
    pivos_anteriores = params.get("pivos_atuais", [])

    # Detecta os pivôs fora da cobertura usando a nova imagem da repetidora
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
                    imagem_path = imagem_path.replace("https://version-test.onrender.com/", "")

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
    import httpx

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

    elev1 = elevs[0] + alt1
    elev2 = elevs[-1] + alt2
    linha_visada = [elev1 + i * (elev2 - elev1) / steps for i in range(steps + 1)]

    margem_m = 1.5
    bloqueio = None
    debug_lista = []

    for i in range(1, steps):
        dif = elevs[i] - linha_visada[i]
        debug_lista.append({
            "i": i,
            "elev": elevs[i],
            "visada": linha_visada[i],
            "dif": round(dif, 2)
        })
        if dif > margem_m:
            bloqueio = {
                "lat": amostrados[i][0],
                "lon": amostrados[i][1],
                "elev": elevs[i],
                "visada": linha_visada[i],
                "dif": round(dif, 2)
            }
            break

    return {
        "bloqueio": bloqueio,
        "elevacao": elevs,
        "linha_visada": linha_visada,
        "status": "Bloqueado" if bloqueio else "Visada limpa",
        "debug": debug_lista[:5] + [{"...": "omitido"}] + debug_lista[-5:]
    }

app.mount("/static", StaticFiles(directory="static"), name="static")

# Endpoint inteligente: sugerir_repetidora_progressiva
@app.post("/sugerir_repetidora_progressiva")
async def sugerir_repetidora_progressiva(req: dict = Body(...)):
    pivos = req.get("pivos", [])
    torre = req.get("torre", {})
    alt_torre = torre.get("altura", 15)
    alt_receiver = torre.get("altura_receiver", 3)

    if not torre or not pivos:
        return {"erro": "Dados insuficientes: torre e pivos obrigatórios"}

    def distancia(a, b):
        return sqrt((a["lat"] - b["lat"])**2 + (a["lon"] - b["lon"])**2) * 111000

    async def tem_visada(a, b):
        coords = [[a["lat"], a["lon"]], [b["lat"], b["lon"]]]
        payload = {
            "pontos": coords,
            "altura_antena": a.get("altura", alt_torre),
            "altura_receiver": b.get("altura_receiver", alt_receiver)
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post("https://version-test.onrender.com/perfil_elevacao", json=payload)
            resp = r.json()
            return not resp.get("bloqueio")
        except:
            return False

    # Ordena pivôs por distância da torre
    pivos.sort(key=lambda p: distancia(p, torre))

    cobertos = []
    repetidoras = []
    caminhos = []

    for pivo in pivos:
        conectado = False

        # Tenta direto com a torre
        if await tem_visada(torre, pivo):
            caminhos.append({"pivo": pivo["nome"], "recebe_de": "torre"})
            cobertos.append(pivo)
            continue

        # Tenta com outros já cobertos (progressivo)
        for anterior in cobertos[::-1]:
            if await tem_visada(anterior, pivo):
                caminhos.append({"pivo": pivo["nome"], "recebe_de": anterior["nome"]})
                cobertos.append(pivo)
                conectado = True
                break

        if not conectado or distancia(torre, pivo) > 2000:
            # Sugere repetidora no meio entre último coberto e este
            ultimo = cobertos[-1] if cobertos else torre
            lat = (ultimo["lat"] + pivo["lat"]) / 2
            lon = (ultimo["lon"] + pivo["lon"]) / 2

            # Consulta elevação
            url = f"https://api.opentopodata.org/v1/srtm90m?locations={lat},{lon}"
            elev = 0
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(url)
                    elev = r.json()["results"][0]["elevation"]
            except:
                pass

            nome_rep = f"Repetidora_{len(repetidoras) + 1}"
            rep = {"lat": lat, "lon": lon, "elev": elev, "nome": nome_rep, "entre": [ultimo["nome"], pivo["nome"]]}
            repetidoras.append(rep)
            caminhos.append({"pivo": pivo["nome"], "recebe_de": nome_rep})
            cobertos.append(pivo)

    return {
        "repetidoras_sugeridas": repetidoras,
        "caminhos_de_sinal": caminhos
    }
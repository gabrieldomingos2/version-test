from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import zipfile, os, xml.etree.ElementTree as ET, httpx, re, json
from PIL import Image
from statistics import mean

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

                        if any(p in nome_texto for p in ["antena", "torre", "barrac\u00e3o", "galp\u00e3o", "silo", "repetidora"]):
                            match = re.search(r"(\d{1,3})\s*(m|metros)", nome.text.lower())
                            altura = int(match.group(1)) if match else 15
                            antena = {"lat": lat, "lon": lon, "altura": altura, "nome": nome.text}
                        elif "piv\u00f4" in nome_texto:
                            pivos.append({"nome": nome.text.strip(), "lat": lat, "lon": lon})
                        elif "casa de bomba" in nome_texto or "irripump" in nome_texto:
                            bombas.append({"nome": nome.text.strip(), "lat": lat, "lon": lon})

                    linha = placemark.find(".//kml:LineString/kml:coordinates", ns)
                    if nome is not None and linha is not None and "medida do c\u00edrculo" in nome.text.lower():
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

        nome_normalizado = nome.lower().replace("medida do c\u00edrculo", "").strip()
        nome_virtual = f"Piv\u00f4 {nome_normalizado}".strip()

        if nome_virtual.lower() in nomes_existentes:
            continue

        max_dist = 0
        ponto_a = coords[0]
        ponto_b = coords[1] if len(coords) > 1 else coords[0]

        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                lat1, lon1 = coords[i]
                lat2, lon2 = coords[j]
                dist = ((lat1 - lat2)**2 + (lon1 - lon2)**2) ** 0.5
                if dist > max_dist:
                    max_dist = dist
                    ponto_a = coords[i]
                    ponto_b = coords[j]

        if max_dist > 0.0005:
            centro_lat = (ponto_a[0] + ponto_b[0]) / 2
            centro_lon = (ponto_a[1] + ponto_b[1]) / 2
        else:
            lats = [lat for lat, lon in coords]
            lons = [lon for lat, lon in coords]
            centro_lat = mean(lats)
            centro_lon = mean(lons)

        if not re.search(r"\d+", nome_virtual):
            nome_virtual = f"Piv\u00f4 {contador_virtual}"
            contador_virtual += 1

        pivos.append({
            "nome": nome_virtual,
            "lat": centro_lat,
            "lon": centro_lon
        })

        print(f"[DEBUG] {nome_virtual} \u2192 Lat: {centro_lat:.6f}, Lon: {centro_lon:.6f}")

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


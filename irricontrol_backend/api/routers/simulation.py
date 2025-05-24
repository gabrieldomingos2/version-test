from fastapi import APIRouter, HTTPException, Depends, Request
import httpx
import os
import json
from typing import List, Optional
from main import STATIC_DIR

# ✅ Corrigido os imports
from core.config import API_URL as CLOUDRF_API_URL, API_KEY as CLOUDRF_API_KEY, obter_template
from models.simulation import (
    SimularSinalRequest, SimularManualRequest, ReavaliarPivosRequest, PerfilElevacaoRequest,
    SimulationResponse, PerfilElevacaoResponse, ReavaliarPivosResponse, PivoData,
    OverlayData, BloqueioData
)
from services.image_analysis import detectar_pivos_fora
from api.deps import get_http_session


router = APIRouter()

STATIC_IMAGENS_DIR = os.path.join(STATIC_DIR, "imagens")
os.makedirs(STATIC_IMAGENS_DIR, exist_ok=True)

def format_coord_for_filename(coord: float) -> str:
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

async def _call_cloudrf_api(payload: dict, client: httpx.AsyncClient):
    headers = {"key": CLOUDRF_API_KEY, "Content-Type": "application/json"}
    try:
        # Aumentado o timeout para chamadas mais longas
        response = await client.post(CLOUDRF_API_URL, headers=headers, json=payload, timeout=90.0) 
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ Erro na API CloudRF: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Erro na API CloudRF: {e.response.text}")
    except httpx.RequestError as e:
        print(f"❌ Erro de requisição para CloudRF: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar à API CloudRF: {str(e)}")
    except json.JSONDecodeError as e_json:
        # Adicionado 'e' para o contexto do erro
        print(f"❌ Erro ao decodificar JSON da CloudRF. Resposta: {e_json.response.text[:500]}")
        raise HTTPException(status_code=500, detail="Resposta inválida (não JSON) da API CloudRF.")

async def _download_and_save_image(image_url: str, local_path: str, client: httpx.AsyncClient):
    try:
        # Aumentado o timeout para downloads
        r = await client.get(image_url, timeout=90.0)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(r.content)
        print(f"✅ Imagem salva em {local_path}")
    except httpx.HTTPStatusError as e:
        print(f"❌ Erro ao baixar imagem {image_url}: Status {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Falha ao baixar imagem de sinal: {e.response.text}")
    except httpx.RequestError as e:
        print(f"❌ Erro de requisição ao baixar imagem {image_url}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Não foi possível baixar a imagem: {str(e)}")

# Função auxiliar para pegar a URL base (para evitar problemas no OnRender)
def get_base_url(http_request: Request) -> str:
    base_url = os.getenv('BACKEND_URL_FOR_FRONTEND')
    if not base_url:
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
        print(f"Aviso: BACKEND_URL_FOR_FRONTEND não definida. Usando URL construída: {base_url}")
    return base_url

@router.post("/simular_sinal", response_model=SimulationResponse, tags=["Simulation"])
async def simular_sinal_endpoint(request_data: SimularSinalRequest, http_request: Request, client: httpx.AsyncClient = Depends(get_http_session)):
    print(f"📡 Simulação Sinal Principal recebida para: {request_data.nome or 'Antena Padrão'}")
    try:
        tpl = obter_template(request_data.template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Limpeza de arquivos antigos (código mantido)
    for f_name in os.listdir(STATIC_IMAGENS_DIR):
        if f_name.startswith("sinal_") and (f_name.endswith(".png") or f_name.endswith(".json")):
            try:
                os.remove(os.path.join(STATIC_IMAGENS_DIR, f_name))
            except OSError as e_remove:
                print(f"Aviso: Não foi possível remover arquivo antigo {f_name}: {e_remove}")

    payload = { # (código mantido)
        "version": "CloudRF-API-v3.24", "site": tpl["site"], "network": "Network", "engine": 2, "coordinates": 1,
        "transmitter": {"lat": request_data.lat, "lon": request_data.lon, "alt": request_data.altura, "frq": tpl["frq"], "txw": tpl["transmitter"]["txw"], "bwi": tpl["transmitter"]["bwi"], "powerUnit": "W"},
        "receiver": tpl["receiver"], "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {**tpl["antenna"], "mode": "template", "txl": 0, "ant": 1, "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "pol": "v"},
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "obstacles": 0, "clt": "Minimal.clt"},
        "output": {"units": "m", "col": tpl["col"], "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10}
    }

    cloudrf_data = await _call_cloudrf_api(payload, client)
    imagem_url = cloudrf_data.get("PNG_WGS84")
    bounds = cloudrf_data.get("bounds")

    # --- INÍCIO DA CORREÇÃO ---
    if not imagem_url or not bounds or len(bounds) != 4:
        raise HTTPException(status_code=500, detail="Resposta da API CloudRF inválida (sem URL/Bounds).")

    south, west, north, east = bounds[0], bounds[1], bounds[2], bounds[3]
    if north < south:
        print(f"⚠️  Bounds Norte/Sul invertidos detectados! (N:{north} < S:{south}). Corrigindo...")
        bounds = [north, west, south, east] # Inverte N e S
    # --- FIM DA CORREÇÃO ---

    lat_str = format_coord_for_filename(request_data.lat)
    lon_str = format_coord_for_filename(request_data.lon)
    nome_arquivo_base = f"sinal_{tpl['id'].lower()}_{lat_str}_{lon_str}"
    caminho_imagem_local = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.png")
    caminho_json_bounds = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.json")

    await _download_and_save_image(imagem_url, caminho_imagem_local, client)
    with open(caminho_json_bounds, "w") as f:
        json.dump({"bounds": bounds}, f) # Salva bounds corrigidos

    pivos_com_status = detectar_pivos_fora(bounds, [p.model_dump() for p in request_data.pivos_atuais], caminho_imagem_local)

    url_imagem_publica = f"{get_base_url(http_request)}/static/imagens/{nome_arquivo_base}.png"

    return SimulationResponse(
        imagem_salva=url_imagem_publica,
        bounds=bounds, # Retorna bounds corrigidos
        status="Simulação da antena principal concluída",
        pivos=pivos_com_status
    )


@router.post("/simular_manual", response_model=SimulationResponse, tags=["Simulation"])
async def simular_manual_endpoint(request_data: SimularManualRequest, http_request: Request, client: httpx.AsyncClient = Depends(get_http_session)):
    print(f"📡 Simulação Manual (Repetidora) recebida para Lat: {request_data.lat}, Lon: {request_data.lon}")
    try:
        tpl = obter_template(request_data.template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Limpeza (código mantido)
    for f_name in os.listdir(STATIC_IMAGENS_DIR):
        if f_name.startswith("repetidora_") and (f_name.endswith(".png") or f_name.endswith(".json")):
            try:
                os.remove(os.path.join(STATIC_IMAGENS_DIR, f_name))
            except OSError as e_remove:
                print(f"Aviso: Não foi possível remover arquivo antigo {f_name}: {e_remove}")
                
    payload = { # (código mantido)
        "version": "CloudRF-API-v3.24", "site": tpl["site"], "network": "Modo Expert", "engine": 2, "coordinates": 1,
        "transmitter": {"lat": request_data.lat, "lon": request_data.lon, "alt": request_data.altura, "frq": tpl["frq"], "txw": tpl["transmitter"]["txw"], "bwi": tpl["transmitter"]["bwi"], "powerUnit": "W"},
        "receiver": {**tpl["receiver"], "alt": request_data.altura_receiver},
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {**tpl["antenna"], "mode": "template", "txl": 0, "ant": 1, "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "pol": "v"},
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "obstacles": 0, "clt": "Minimal.clt"},
        "output": {"units": "m", "col": tpl["col"], "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10}
    }

    cloudrf_data = await _call_cloudrf_api(payload, client)
    imagem_url = cloudrf_data.get("PNG_WGS84")
    bounds = cloudrf_data.get("bounds")

    # --- INÍCIO DA CORREÇÃO ---
    if not imagem_url or not bounds or len(bounds) != 4:
        raise HTTPException(status_code=500, detail="Resposta da API CloudRF inválida (sem URL/Bounds).")

    south, west, north, east = bounds[0], bounds[1], bounds[2], bounds[3]
    if north < south:
        print(f"⚠️  Bounds Norte/Sul invertidos detectados! (N:{north} < S:{south}). Corrigindo...")
        bounds = [north, west, south, east] # Inverte N e S
    # --- FIM DA CORREÇÃO ---

    lat_str = format_coord_for_filename(request_data.lat)
    lon_str = format_coord_for_filename(request_data.lon)
    nome_arquivo_base = f"repetidora_{tpl['id'].lower()}_{lat_str}_{lon_str}"
    caminho_imagem_local = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.png")
    caminho_json_bounds = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.json")

    await _download_and_save_image(imagem_url, caminho_imagem_local, client)
    with open(caminho_json_bounds, "w") as f:
        json.dump({"bounds": bounds}, f) # Salva bounds corrigidos

    pivos_com_status_nesta_imagem = detectar_pivos_fora(bounds, [p.model_dump() for p in request_data.pivos_atuais], caminho_imagem_local)

    url_imagem_publica = f"{get_base_url(http_request)}/static/imagens/{nome_arquivo_base}.png"

    return SimulationResponse(
        imagem_salva=url_imagem_publica,
        bounds=bounds, # Retorna bounds corrigidos
        status="Simulação da repetidora concluída",
        pivos=pivos_com_status_nesta_imagem
    )


@router.post("/reavaliar_pivos", response_model=ReavaliarPivosResponse, tags=["Simulation"])
async def reavaliar_pivos_endpoint(request_data: ReavaliarPivosRequest):
    pivos_input = request_data.pivos
    overlays_input = request_data.overlays
    pivos_cobertura_final = {p.nome: False for p in pivos_input}

    for overlay_data in overlays_input:
        bounds = overlay_data.bounds

        # --- INÍCIO DA CORREÇÃO (Também aqui por segurança) ---
        if not bounds or len(bounds) != 4:
            print(f"Aviso: Bounds inválidos recebidos em /reavaliar_pivos. Pulando overlay.")
            continue
            
        south, west, north, east = bounds[0], bounds[1], bounds[2], bounds[3]
        if north < south:
            print(f"⚠️  Bounds Norte/Sul invertidos detectados em /reavaliar_pivos! Corrigindo...")
            bounds = [north, west, south, east]
        # --- FIM DA CORREÇÃO ---

        imagem_url_completa = overlay_data.imagem
        nome_arquivo_imagem = imagem_url_completa.split('/')[-1]
        caminho_imagem_servidor = os.path.join(STATIC_IMAGENS_DIR, nome_arquivo_imagem)

        if not os.path.exists(caminho_imagem_servidor):
            print(f"Aviso: Imagem para reavaliação não encontrada: {caminho_imagem_servidor}")
            continue

        pivos_para_checar_neste_overlay = [p for p in pivos_input if not pivos_cobertura_final[p.nome]]
        if not pivos_para_checar_neste_overlay:
            break

        pivos_status_neste_overlay = detectar_pivos_fora(
            bounds, # Usa bounds corrigidos
            [p.model_dump() for p in pivos_para_checar_neste_overlay],
            caminho_imagem_servidor
        )

        for p_status in pivos_status_neste_overlay:
            if not p_status["fora"]:
                pivos_cobertura_final[p_status["nome"]] = True

    pivos_resultado_final = [
        PivoData(nome=p.nome, lat=p.lat, lon=p.lon, fora=not pivos_cobertura_final[p.nome])
        for p in pivos_input
    ]

    return ReavaliarPivosResponse(pivos=pivos_resultado_final)


@router.post("/perfil_elevacao", response_model=PerfilElevacaoResponse, tags=["Simulation"])
async def perfil_elevacao_endpoint(request_data: PerfilElevacaoRequest, client: httpx.AsyncClient = Depends(get_http_session)):
    pontos = request_data.pontos
    alt1 = request_data.altura_antena
    alt2 = request_data.altura_receiver

    if len(pontos) < 2 or len(pontos[0]) < 2 or len(pontos[1]) < 2:
        raise HTTPException(status_code=400, detail="Informe pelo menos dois pontos com [lat, lon].")

    steps = 50
    amostrados = [
        (pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / steps,
         pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / steps)
        for i in range(steps + 1)
    ]

    coords_param = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in amostrados])
    url_opentopo = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

    try:
        resp_opentopo = await client.get(url_opentopo, timeout=60.0) # Aumentado timeout
        resp_opentopo.raise_for_status()
        dados_opentopo = resp_opentopo.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Erro na API OpenTopoData: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar à API OpenTopoData: {str(e)}")

    elevs = []
    results = dados_opentopo.get("results", [])
    for r_idx, r in enumerate(results):
        elev = r.get("elevation")
        if elev is None:
            print(f"Aviso: Elevação nula em OpenTopoData no ponto {r_idx}. Tentando vizinhos.")
            if r_idx > 0 and elevs: elev = elevs[-1]
            elif len(results) > r_idx + 1 and results[r_idx+1].get("elevation") is not None: elev = results[r_idx+1].get("elevation")
            else: elev = 0
        elevs.append(elev)

    if len(elevs) != (steps + 1):
        raise HTTPException(status_code=500, detail="Número inesperado de resultados de elevação.")

    elev1_com_antena = elevs[0] + alt1
    elev2_com_receiver = elevs[-1] + alt2
    linha_visada_calculada = [elev1_com_antena + i * (elev2_com_receiver - elev1_com_antena) / steps for i in range(steps + 1)]

    max_diff_bloqueio = 0
    ponto_bloqueio_calculado: Optional[BloqueioData] = None

    for i in range(1, steps):
        diff = elevs[i] - linha_visada_calculada[i]
        if diff > 0 and diff > max_diff_bloqueio:
            max_diff_bloqueio = diff
            ponto_bloqueio_calculado = BloqueioData(lat=amostrados[i][0], lon=amostrados[i][1], elev=elevs[i])

    return PerfilElevacaoResponse(bloqueio=ponto_bloqueio_calculado, elevacao=elevs)
from fastapi import APIRouter, HTTPException, Depends
import httpx
import os
import json
from typing import List

from app.core.config import API_URL as CLOUDRF_API_URL, API_KEY as CLOUDRF_API_KEY, obter_template
from app.models.simulation import (
    SimularSinalRequest, SimularManualRequest, ReavaliarPivosRequest, PerfilElevacaoRequest,
    SimulationResponse, PerfilElevacaoResponse, ReavaliarPivosResponse, PivoData
)
from app.services.image_analysis import detectar_pivos_fora
from app.api.deps import get_http_session # Para cliente HTTP compartilhado

router = APIRouter()

# Pasta para salvar imagens e bounds, relativa à raiz do projeto backend
STATIC_IMAGENS_DIR = "static/imagens"
# Garante que o diretório de imagens exista
os.makedirs(STATIC_IMAGENS_DIR, exist_ok=True)


# Função auxiliar para formatar coordenadas (movida para utils, mas pode ser usada aqui se preferir)
def format_coord_for_filename(coord: float) -> str:
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

async def _call_cloudrf_api(payload: dict, client: httpx.AsyncClient):
    headers = {"key": CLOUDRF_API_KEY, "Content-Type": "application/json"}
    try:
        response = await client.post(CLOUDRF_API_URL, headers=headers, json=payload)
        response.raise_for_status() # Lança exceção para erros HTTP 4xx/5xx
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ Erro na API CloudRF: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Erro na API CloudRF: {e.response.text}")
    except httpx.RequestError as e:
        print(f"❌ Erro de requisição para CloudRF: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar à API CloudRF: {str(e)}")
    except json.JSONDecodeError:
        print(f"❌ Erro ao decodificar JSON da CloudRF. Resposta: {response.text[:500]}") # Loga parte da resposta
        raise HTTPException(status_code=500, detail="Resposta inválida (não JSON) da API CloudRF.")


async def _download_and_save_image(image_url: str, local_path: str, client: httpx.AsyncClient):
    try:
        r = await client.get(image_url) # Timeout já está no cliente
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


@router.post("/simular_sinal", response_model=SimulationResponse, tags=["Simulation"])
async def simular_sinal_endpoint(request_data: SimularSinalRequest, client: httpx.AsyncClient = Depends(get_http_session)):
    print(f"📡 Simulação Sinal Principal recebida para: {request_data.nome or 'Antena Padrão'}")
    try:
        tpl = obter_template(request_data.template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Limpa arquivos antigos de SINAL PRINCIPAL (sinal_*)
    for f_name in os.listdir(STATIC_IMAGENS_DIR):
        if f_name.startswith("sinal_") and (f_name.endswith(".png") or f_name.endswith(".json")):
            try:
                os.remove(os.path.join(STATIC_IMAGENS_DIR, f_name))
            except OSError as e_remove:
                print(f"Aviso: Não foi possível remover arquivo antigo {f_name}: {e_remove}")


    payload = {
        "version": "CloudRF-API-v3.24", "site": tpl["site"], "network": "Network", "engine": 2, "coordinates": 1,
        "transmitter": {
            "lat": request_data.lat, "lon": request_data.lon, "alt": request_data.altura,
            "frq": tpl["frq"], "txw": tpl["transmitter"]["txw"], "bwi": tpl["transmitter"]["bwi"], "powerUnit": "W"
        },
        "receiver": tpl["receiver"], "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {**tpl["antenna"], "mode": "template", "txl": 0, "ant": 1, "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "pol": "v"},
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "obstacles": 0, "clt": "Minimal.clt"},
        "output": {"units": "m", "col": tpl["col"], "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10}
    }

    cloudrf_data = await _call_cloudrf_api(payload, client)
    imagem_url = cloudrf_data.get("PNG_WGS84")
    bounds = cloudrf_data.get("bounds")

    if not imagem_url or not bounds:
        raise HTTPException(status_code=500, detail="Resposta da API CloudRF não continha URL da imagem ou bounds.")

    lat_str = format_coord_for_filename(request_data.lat)
    lon_str = format_coord_for_filename(request_data.lon)
    nome_arquivo_base = f"sinal_{tpl['id'].lower()}_{lat_str}_{lon_str}"
    caminho_imagem_local = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.png")
    caminho_json_bounds = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.json")

    await _download_and_save_image(imagem_url, caminho_imagem_local, client)
    with open(caminho_json_bounds, "w") as f:
        json.dump({"bounds": bounds}, f)

    pivos_com_status = detectar_pivos_fora(bounds, [p.model_dump() for p in request_data.pivos_atuais], caminho_imagem_local)
    
    # URL pública para o frontend acessar a imagem
    url_imagem_publica = f"{os.getenv('BACKEND_URL_FOR_FRONTEND', 'https://irricontrol-test.onrender.com')}/static/imagens/{nome_arquivo_base}.png"


    return SimulationResponse(
        imagem_salva=url_imagem_publica,
        bounds=bounds,
        status="Simulação da antena principal concluída",
        pivos=pivos_com_status
    )


@router.post("/simular_manual", response_model=SimulationResponse, tags=["Simulation"])
async def simular_manual_endpoint(request_data: SimularManualRequest, client: httpx.AsyncClient = Depends(get_http_session)):
    print(f"📡 Simulação Manual (Repetidora) recebida para Lat: {request_data.lat}, Lon: {request_data.lon}")
    try:
        tpl = obter_template(request_data.template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Limpa arquivos antigos de REPETIDORAS (repetidora_*)
    for f_name in os.listdir(STATIC_IMAGENS_DIR):
        if f_name.startswith("repetidora_") and (f_name.endswith(".png") or f_name.endswith(".json")):
            try:
                os.remove(os.path.join(STATIC_IMAGENS_DIR, f_name))
            except OSError as e_remove:
                print(f"Aviso: Não foi possível remover arquivo antigo {f_name}: {e_remove}")

    payload = {
        "version": "CloudRF-API-v3.24", "site": tpl["site"], "network": "Modo Expert", "engine": 2, "coordinates": 1,
        "transmitter": {
            "lat": request_data.lat, "lon": request_data.lon, "alt": request_data.altura,
            "frq": tpl["frq"], "txw": tpl["transmitter"]["txw"], "bwi": tpl["transmitter"]["bwi"], "powerUnit": "W"
        },
        "receiver": {**tpl["receiver"], "alt": request_data.altura_receiver}, # Usa altura_receiver do request
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {**tpl["antenna"], "mode": "template", "txl": 0, "ant": 1, "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "pol": "v"},
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1, "month": 4, "hour": 12, "sunspots_r12": 100},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "obstacles": 0, "clt": "Minimal.clt"},
        "output": {"units": "m", "col": tpl["col"], "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10}
    }

    cloudrf_data = await _call_cloudrf_api(payload, client)
    imagem_url = cloudrf_data.get("PNG_WGS84")
    bounds = cloudrf_data.get("bounds")

    if not imagem_url or not bounds:
        raise HTTPException(status_code=500, detail="Resposta da API CloudRF não continha URL da imagem ou bounds para repetidora.")

    lat_str = format_coord_for_filename(request_data.lat)
    lon_str = format_coord_for_filename(request_data.lon)
    nome_arquivo_base = f"repetidora_{tpl['id'].lower()}_{lat_str}_{lon_str}"
    caminho_imagem_local = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.png")
    caminho_json_bounds = os.path.join(STATIC_IMAGENS_DIR, f"{nome_arquivo_base}.json")

    await _download_and_save_image(imagem_url, caminho_imagem_local, client)
    with open(caminho_json_bounds, "w") as f:
        json.dump({"bounds": bounds}, f)

    # Para simulação manual (repetidora), a detecção de pivôs fora considera apenas ESTA imagem.
    # A lógica de agregação é feita no /reavaliar_pivos
    pivos_com_status_nesta_imagem = detectar_pivos_fora(bounds, [p.model_dump() for p in request_data.pivos_atuais], caminho_imagem_local)
    
    url_imagem_publica = f"{os.getenv('BACKEND_URL_FOR_FRONTEND', 'https://irricontrol-test.onrender.com')}/static/imagens/{nome_arquivo_base}.png"

    return SimulationResponse(
        imagem_salva=url_imagem_publica,
        bounds=bounds,
        status="Simulação da repetidora concluída",
        pivos=pivos_com_status_nesta_imagem # Retorna status para esta repetidora apenas
    )


@router.post("/reavaliar_pivos", response_model=ReavaliarPivosResponse, tags=["Simulation"])
async def reavaliar_pivos_endpoint(request_data: ReavaliarPivosRequest):
    pivos_input = request_data.pivos
    overlays_input = request_data.overlays

    pivos_cobertura_final = {p.nome: False for p in pivos_input} # Assume não coberto inicialmente

    for overlay_data in overlays_input:
        bounds = overlay_data.bounds
        # Converte URL da imagem para caminho local no servidor
        imagem_url_completa = overlay_data.imagem
        nome_arquivo_imagem = imagem_url_completa.split('/')[-1] # Pega só o nome do arquivo
        caminho_imagem_servidor = os.path.join(STATIC_IMAGENS_DIR, nome_arquivo_imagem)

        if not os.path.exists(caminho_imagem_servidor):
            print(f"Aviso: Imagem para reavaliação não encontrada no servidor: {caminho_imagem_servidor}")
            continue

        # Pivôs que ainda não foram marcados como cobertos
        pivos_para_checar_neste_overlay = [p for p in pivos_input if not pivos_cobertura_final[p.nome]]
        if not pivos_para_checar_neste_overlay: # Todos já cobertos
            break

        # `detectar_pivos_fora` retorna uma lista, onde pivo['fora'] é True se NÃO coberto pela imagem
        pivos_status_neste_overlay = detectar_pivos_fora(
            bounds,
            [p.model_dump() for p in pivos_para_checar_neste_overlay],
            caminho_imagem_servidor
        )

        for p_status in pivos_status_neste_overlay:
            if not p_status["fora"]: # Se está coberto por esta imagem
                pivos_cobertura_final[p_status["nome"]] = True

    # Monta a lista final de pivôs com o status de cobertura agregado
    pivos_resultado_final = []
    for p_input in pivos_input:
        pivos_resultado_final.append(PivoData(
            nome=p_input.nome,
            lat=p_input.lat,
            lon=p_input.lon,
            fora=not pivos_cobertura_final[p_input.nome]
        ))

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
        (
            pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / steps, # Latitude
            pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / steps  # Longitude
        )
        for i in range(steps + 1)
    ]

    coords_param = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in amostrados])
    url_opentopo = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

    try:
        resp_opentopo = await client.get(url_opentopo)
        resp_opentopo.raise_for_status()
        dados_opentopo = resp_opentopo.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Erro na API OpenTopoData: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar à API OpenTopoData: {str(e)}")

    elevs = []
    for r_idx, r in enumerate(dados_opentopo.get("results", [])):
        if r.get("elevation") is None:
            # Tenta pegar do vizinho ou default para 0 se for borda
            if r_idx > 0 and elevs:
                elevs.append(elevs[-1])
                print(f"Aviso: Elevação nula em OpenTopoData no ponto {r_idx}, usando anterior: {elevs[-1]}")
            elif len(dados_opentopo.get("results", [])) > r_idx + 1 and dados_opentopo["results"][r_idx+1].get("elevation") is not None:
                elevs.append(dados_opentopo["results"][r_idx+1].get("elevation")) #Usa o próximo
                print(f"Aviso: Elevação nula em OpenTopoData no ponto {r_idx}, usando próximo: {elevs[-1]}")
            else:
                 elevs.append(0) # Fallback para 0
                 print(f"Aviso: Elevação nula em OpenTopoData no ponto {r_idx}, usando 0.")

        else:
            elevs.append(r["elevation"])


    if len(elevs) != (steps + 1):
         raise HTTPException(status_code=500, detail="Número inesperado de resultados de elevação da OpenTopoData.")


    elev1_com_antena = elevs[0] + alt1
    elev2_com_receiver = elevs[-1] + alt2
    linha_visada_calculada = [
        elev1_com_antena + i * (elev2_com_receiver - elev1_com_antena) / steps
        for i in range(steps + 1)
    ]

    max_diff_bloqueio = 0
    ponto_bloqueio_calculado: Optional[BloqueioData] = None

    for i in range(1, steps): # Exclui os pontos inicial e final da antena/receiver
        elev_terreno_atual = elevs[i]
        elev_linha_visada_atual = linha_visada_calculada[i]
        diff = elev_terreno_atual - elev_linha_visada_atual
        if diff > 0 and diff > max_diff_bloqueio: # Se o terreno está acima da linha de visada
            max_diff_bloqueio = diff
            ponto_bloqueio_calculado = BloqueioData(
                lat=amostrados[i][0],
                lon=amostrados[i][1],
                elev=elev_terreno_atual
            )

    return PerfilElevacaoResponse(bloqueio=ponto_bloqueio_calculado, elevacao=elevs)
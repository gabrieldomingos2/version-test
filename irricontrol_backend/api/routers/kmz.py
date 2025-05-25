from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse
import os
import json
import simplekml
from datetime import datetime
import zipfile
from typing import Optional, List


from services.kmz_parser import parse_kmz
from models.simulation import ProcessKmzResponse # Importa modelos Pydantic
from core.paths import STATIC_IMAGENS_DIR, ARQUIVOS_DIR  # ✅ CERTO




@router.post("/processar_kmz", response_model=ProcessKmzResponse, tags=["KMZ"])
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    # ... (resto do seu código do endpoint)
    try:
        print("📥 Recebendo arquivo KMZ...") #
        conteudo = await file.read() #

        os.makedirs(ARQUIVOS_DIR, exist_ok=True) #
        caminho_kmz_entrada = os.path.join(ARQUIVOS_DIR, "entrada.kmz") #

        with open(caminho_kmz_entrada, "wb") as f: #
            f.write(conteudo) #
        print("📦 KMZ salvo em:", caminho_kmz_entrada) #

        antena, pivos, ciclos, bombas = parse_kmz(caminho_kmz_entrada) #

        if not antena: #
            raise HTTPException(status_code=400, detail="Antena não encontrada no KMZ")

        return ProcessKmzResponse(antena=antena, pivos=pivos, ciclos=ciclos, bombas=bombas) #

    except HTTPException as http_exc: #
        raise http_exc # Re-levanta HTTPException para ser tratada pelo FastAPI
    except Exception as e: #
        print(f"❌ Erro em /processar_kmz: {str(e)}") #
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {str(e)}")


@router.get("/exportar_kmz", tags=["KMZ"])
def exportar_kmz_endpoint(
    imagem: Optional[str] = Query(None, description="Nome da imagem PNG principal"), #
    bounds_file: Optional[str] = Query(None, description="Nome do JSON de bounds da imagem principal") #
):
    # ... (resto do seu código do endpoint)
    try:
        caminho_kmz_entrada = os.path.join(ARQUIVOS_DIR, "entrada.kmz") #
        if not os.path.exists(caminho_kmz_entrada): #
            raise HTTPException(status_code=404, detail="KMZ de entrada não encontrado. Processe um KMZ primeiro.")

        antena, pivos_parsed, ciclos, _ = parse_kmz(caminho_kmz_entrada) #

        if not antena or not pivos_parsed: #
            raise HTTPException(status_code=400, detail="Antena ou pivôs não encontrados no KMZ original.")

        caminho_imagem_principal_abs = os.path.join(STATIC_IMAGENS_DIR, imagem) if imagem else None #
        caminho_bounds_principal_abs = os.path.join(STATIC_IMAGENS_DIR, bounds_file) if bounds_file else None #

        bounds_principal = None #
        if caminho_bounds_principal_abs and os.path.exists(caminho_bounds_principal_abs): #
            with open(caminho_bounds_principal_abs, "r") as f: #
                bounds_data = json.load(f) #
                bounds_principal = bounds_data.get("bounds", bounds_data) #
        elif imagem and not bounds_file: #
            possible_bounds_file = imagem.replace(".png", ".json") #
            caminho_bounds_deduzido = os.path.join(STATIC_IMAGENS_DIR, possible_bounds_file) #
            if os.path.exists(caminho_bounds_deduzido): #
                with open(caminho_bounds_deduzido, "r") as f: #
                    bounds_data = json.load(f) #
                    bounds_principal = bounds_data.get("bounds", bounds_data) #
                    print(f"Info: Bounds deduzido para {imagem} como {possible_bounds_file}") #
            else: #
                 print(f"Aviso: Bounds não fornecido nem deduzido para {imagem}. Overlay principal pode não ser adicionado.") #


        kml = simplekml.Kml(name="Estudo de Cobertura Irricontrol") #

        torre_style = simplekml.Style() #
        torre_style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/T.png" #
        torre_style.iconstyle.scale = 1.2 #

        pnt_torre = kml.newpoint(name=antena.get("nome", "Antena Principal"), #
                                 coords=[(antena["lon"], antena["lat"])]) #
        pnt_torre.description = f"Altura: {antena['altura']}m" #
        pnt_torre.style = torre_style #

        for p in pivos_parsed: #
            pnt_pivo = kml.newpoint(name=p["nome"], coords=[(p["lon"], p["lat"])]) #
            pnt_pivo.description = "Status de cobertura a ser verificado" #
            pnt_pivo.style = torre_style # Reutiliza estilo da torre, pode querer um diferente para pivos #


        for ciclo in ciclos: #
            if ciclo.get("coordenadas"): #
                poly = kml.newpolygon(name=ciclo.get("nome", "Área Pivô")) #
                poly.outerboundaryis = [(lon, lat) for lat, lon in ciclo["coordenadas"]] #
                poly.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.yellow) #
                poly.style.linestyle.color = simplekml.Color.red #
                poly.style.linestyle.width = 2 #

        if caminho_imagem_principal_abs and os.path.exists(caminho_imagem_principal_abs) and bounds_principal: #
            ground = kml.newgroundoverlay(name=f"Cobertura: {antena.get('nome', 'Principal')}") #
            ground.icon.href = imagem #
            ground.latlonbox.north, ground.latlonbox.south = bounds_principal[2], bounds_principal[0] #
            ground.latlonbox.east, ground.latlonbox.west = bounds_principal[3], bounds_principal[1] #
            ground.color = simplekml.Color.changealphaint(180, simplekml.Color.white) #
        
        arquivos_na_pasta_imagens = os.listdir(STATIC_IMAGENS_DIR) #
        imagens_embebidas_kmz = {imagem} if imagem else set() #
        caminho_icone_cloudrf_local = os.path.join(STATIC_IMAGENS_DIR, "cloudrf.png") #
        if os.path.exists(caminho_icone_cloudrf_local): #
             imagens_embebidas_kmz.add("cloudrf.png") #


        for nome_arq_img_rep in arquivos_na_pasta_imagens: #
            if nome_arq_img_rep.startswith("repetidora_") and nome_arq_img_rep.endswith(".png"): #
                nome_arq_json_rep = nome_arq_img_rep.replace(".png", ".json") #
                caminho_json_rep_abs = os.path.join(STATIC_IMAGENS_DIR, nome_arq_json_rep) #

                if os.path.exists(caminho_json_rep_abs): #
                    with open(caminho_json_rep_abs, "r") as f_rep_bounds: #
                        bounds_rep_data = json.load(f_rep_bounds) #
                        bounds_rep = bounds_rep_data.get("bounds", bounds_rep_data) #
                    
                    ground_rep = kml.newgroundoverlay(name=f"Cobertura Repetidora: {nome_arq_img_rep}") #
                    ground_rep.icon.href = nome_arq_img_rep #
                    ground_rep.latlonbox.north, ground_rep.latlonbox.south = bounds_rep[2], bounds_rep[0] #
                    ground_rep.latlonbox.east, ground_rep.latlonbox.west = bounds_rep[3], bounds_rep[1] #
                    ground_rep.color = simplekml.Color.changealphaint(150, simplekml.Color.white) #
                    imagens_embebidas_kmz.add(nome_arq_img_rep) #
                    try: #
                        parts = nome_arq_img_rep.split('_') #
                        lat_rep_str = parts[-2].replace('m','-').replace('_','.') #
                        lon_rep_str = parts[-1].replace('.png','').replace('m','-').replace('_','.') #
                        lat_rep, lon_rep = float(lat_rep_str), float(lon_rep_str) #
                        pnt_rep = kml.newpoint(name=f"Repetidora ({nome_arq_img_rep.split('_')[1]})", coords=[(lon_rep, lat_rep)]) #
                        pnt_rep.style = torre_style #
                    except Exception: # fallback se nome não tem coords #
                        lat_rep_centro = (bounds_rep[0] + bounds_rep[2]) / 2 #
                        lon_rep_centro = (bounds_rep[1] + bounds_rep[3]) / 2 #
                        pnt_rep = kml.newpoint(name=f"Repetidora ({nome_arq_img_rep.split('_')[1]})", coords=[(lon_rep_centro, lat_rep_centro)]) #
                        pnt_rep.style = torre_style #


        os.makedirs(ARQUIVOS_DIR, exist_ok=True) #
        caminho_kml_saida = os.path.join(ARQUIVOS_DIR, "estudo_irricontrol.kml") #
        kml.save(caminho_kml_saida) #

        nome_arquivo_kmz = f"EstudoIrricontrol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz" #
        caminho_kmz_final = os.path.join(ARQUIVOS_DIR, nome_arquivo_kmz) #

        with zipfile.ZipFile(caminho_kmz_final, 'w', zipfile.ZIP_DEFLATED) as kmz_zip: #
            kmz_zip.write(caminho_kml_saida, os.path.basename(caminho_kml_saida)) #
            
            for img_nome_relativo in imagens_embebidas_kmz: #
                if img_nome_relativo: #
                    caminho_img_abs = os.path.join(STATIC_IMAGENS_DIR, img_nome_relativo) #
                    if os.path.exists(caminho_img_abs): #
                        kmz_zip.write(caminho_img_abs, img_nome_relativo) #
                    else: #
                        print(f"Aviso: Imagem {img_nome_relativo} não encontrada para adicionar ao KMZ.") #


        return FileResponse(caminho_kmz_final, media_type="application/vnd.google-earth.kmz", filename=nome_arquivo_kmz) #

    except HTTPException as http_exc: #
        raise http_exc #
    except Exception as e: #
        print(f"❌ Erro em /exportar_kmz: {str(e)}") #
        raise HTTPException(status_code=500, detail=f"Erro interno ao exportar KMZ: {str(e)}")
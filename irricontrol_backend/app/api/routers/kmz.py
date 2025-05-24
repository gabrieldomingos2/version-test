from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse
import os
import json
import simplekml
from datetime import datetime
import zipfile # Adicionado para criação de KMZ

from app.services.kmz_parser import parse_kmz
from app.models.simulation import ProcessKmzResponse # Importa modelos Pydantic

router = APIRouter()

# Pasta para arquivos temporários, deve existir na raiz do projeto backend
ARQUIVOS_DIR = "arquivos"
STATIC_IMAGENS_DIR = "static/imagens"


@router.post("/processar_kmz", response_model=ProcessKmzResponse, tags=["KMZ"])
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    try:
        print("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()

        os.makedirs(ARQUIVOS_DIR, exist_ok=True)
        caminho_kmz_entrada = os.path.join(ARQUIVOS_DIR, "entrada.kmz")

        with open(caminho_kmz_entrada, "wb") as f:
            f.write(conteudo)
        print("📦 KMZ salvo em:", caminho_kmz_entrada)

        antena, pivos, ciclos, bombas = parse_kmz(caminho_kmz_entrada)

        if not antena:
            raise HTTPException(status_code=400, detail="Antena não encontrada no KMZ")

        # Salvar contorno da fazenda (opcional, se ciclos existem)
        # if ciclos:
        #     maior_ciclo = max(ciclos, key=lambda c: len(c.get("coordenadas", [])))
        #     if maior_ciclo.get("coordenadas"):
        #         coords_fazenda = [[lon, lat] for lat, lon in maior_ciclo["coordenadas"]]
        #         # Este path precisa ser acessível pelo StaticFiles
        #         # Se StaticFiles serve 'static/', então o path deve ser relativo a 'static/'
        #         os.makedirs(STATIC_IMAGENS_DIR, exist_ok=True) # Garante que a pasta de imagens existe
        #         path_contorno = os.path.join(STATIC_IMAGENS_DIR, "contorno_fazenda.json")
        #         with open(path_contorno, "w") as f_contorno:
        #             json.dump(coords_fazenda, f_contorno)


        return ProcessKmzResponse(antena=antena, pivos=pivos, ciclos=ciclos, bombas=bombas)

    except HTTPException as http_exc:
        raise http_exc # Re-levanta HTTPException para ser tratada pelo FastAPI
    except Exception as e:
        print(f"❌ Erro em /processar_kmz: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {str(e)}")


@router.get("/exportar_kmz", tags=["KMZ"])
def exportar_kmz_endpoint(
    imagem: Optional[str] = Query(None, description="Nome da imagem PNG principal"),
    bounds_file: Optional[str] = Query(None, description="Nome do JSON de bounds da imagem principal")
):
    try:
        caminho_kmz_entrada = os.path.join(ARQUIVOS_DIR, "entrada.kmz")
        if not os.path.exists(caminho_kmz_entrada):
            raise HTTPException(status_code=404, detail="KMZ de entrada não encontrado. Processe um KMZ primeiro.")

        antena, pivos_parsed, ciclos, _ = parse_kmz(caminho_kmz_entrada) # Pegamos pivos parseados para ter os nomes corretos

        if not antena or not pivos_parsed: # Mudado para pivos_parsed
            raise HTTPException(status_code=400, detail="Antena ou pivôs não encontrados no KMZ original.")

        # Caminhos para a imagem principal e seus bounds (se fornecidos)
        caminho_imagem_principal_abs = os.path.join(STATIC_IMAGENS_DIR, imagem) if imagem else None
        caminho_bounds_principal_abs = os.path.join(STATIC_IMAGENS_DIR, bounds_file) if bounds_file else None

        bounds_principal = None
        if caminho_bounds_principal_abs and os.path.exists(caminho_bounds_principal_abs):
            with open(caminho_bounds_principal_abs, "r") as f:
                bounds_data = json.load(f)
                bounds_principal = bounds_data.get("bounds", bounds_data) # Aceita ambos os formatos
        elif imagem and not bounds_file: # Se imagem foi dada mas bounds não, tenta deduzir
            possible_bounds_file = imagem.replace(".png", ".json")
            caminho_bounds_deduzido = os.path.join(STATIC_IMAGENS_DIR, possible_bounds_file)
            if os.path.exists(caminho_bounds_deduzido):
                with open(caminho_bounds_deduzido, "r") as f:
                    bounds_data = json.load(f)
                    bounds_principal = bounds_data.get("bounds", bounds_data)
                    print(f"Info: Bounds deduzido para {imagem} como {possible_bounds_file}")
            else:
                 print(f"Aviso: Bounds não fornecido nem deduzido para {imagem}. Overlay principal pode não ser adicionado.")


        kml = simplekml.Kml(name="Estudo de Cobertura Irricontrol")

        # Estilos
        torre_style = simplekml.Style()
        torre_style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/T.png" # Ícone de Torre
        torre_style.iconstyle.scale = 1.2

        pivo_coberto_style = simplekml.Style()
        pivo_coberto_style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
        pivo_coberto_style.iconstyle.scale = 0.8

        pivo_fora_style = simplekml.Style()
        pivo_fora_style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
        pivo_fora_style.iconstyle.scale = 0.8
        
        # Adicionar ícone cloudrf.png ao KMZ se ele for usado para repetidoras
        caminho_icone_cloudrf_local = os.path.join(STATIC_IMAGENS_DIR, "cloudrf.png")


        # Torre principal
        pnt_torre = kml.newpoint(name=antena.get("nome", "Antena Principal"),
                                 coords=[(antena["lon"], antena["lat"])])
        pnt_torre.description = f"Altura: {antena['altura']}m"
        pnt_torre.style = torre_style

        # Pivôs - Usar pivos_parsed para nomes e coords originais, status pode vir de um arquivo de status
        # Por simplicidade, vamos assumir que o status "fora" não está disponível aqui, ou precisaria ser lido de um arquivo
        for p in pivos_parsed:
            pnt_pivo = kml.newpoint(name=p["nome"], coords=[(p["lon"], p["lat"])])
            # A descrição do status de cobertura idealmente viria de uma simulação recente
            # Aqui, vamos deixar genérico ou você pode tentar ler um arquivo de status
            pnt_pivo.description = "Status de cobertura a ser verificado"
            pnt_pivo.style = pivo_coberto_style # Default para coberto, ajuste se tiver dados de status

        # Círculos (Geometrias dos Pivôs)
        for ciclo in ciclos:
            if ciclo.get("coordenadas"):
                poly = kml.newpolygon(name=ciclo.get("nome", "Área Pivô"))
                poly.outerboundaryis = [(lon, lat) for lat, lon in ciclo["coordenadas"]] # KML é Lon, Lat
                poly.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.yellow) # Amarelo semi-transparente
                poly.style.linestyle.color = simplekml.Color.red
                poly.style.linestyle.width = 2

        # Overlay da torre principal
        if caminho_imagem_principal_abs and os.path.exists(caminho_imagem_principal_abs) and bounds_principal:
            ground = kml.newgroundoverlay(name=f"Cobertura: {antena.get('nome', 'Principal')}")
            ground.icon.href = imagem # Nome relativo para o KMZ
            ground.latlonbox.north, ground.latlonbox.south = bounds_principal[2], bounds_principal[0]
            ground.latlonbox.east, ground.latlonbox.west = bounds_principal[3], bounds_principal[1]
            ground.color = simplekml.Color.changealphaint(180, simplekml.Color.white) # Opacidade (0-255)
        
        # Adicionar overlays e pontos de repetidoras
        arquivos_na_pasta_imagens = os.listdir(STATIC_IMAGENS_DIR)
        imagens_embebidas_kmz = {imagem} if imagem else set() # Para não duplicar
        if os.path.exists(caminho_icone_cloudrf_local):
             imagens_embebidas_kmz.add("cloudrf.png")


        for nome_arq_img_rep in arquivos_na_pasta_imagens:
            if nome_arq_img_rep.startswith("repetidora_") and nome_arq_img_rep.endswith(".png"):
                nome_arq_json_rep = nome_arq_img_rep.replace(".png", ".json")
                caminho_json_rep_abs = os.path.join(STATIC_IMAGENS_DIR, nome_arq_json_rep)

                if os.path.exists(caminho_json_rep_abs):
                    with open(caminho_json_rep_abs, "r") as f_rep_bounds:
                        bounds_rep_data = json.load(f_rep_bounds)
                        bounds_rep = bounds_rep_data.get("bounds", bounds_rep_data)
                    
                    ground_rep = kml.newgroundoverlay(name=f"Cobertura Repetidora: {nome_arq_img_rep}")
                    ground_rep.icon.href = nome_arq_img_rep # Nome relativo
                    ground_rep.latlonbox.north, ground_rep.latlonbox.south = bounds_rep[2], bounds_rep[0]
                    ground_rep.latlonbox.east, ground_rep.latlonbox.west = bounds_rep[3], bounds_rep[1]
                    ground_rep.color = simplekml.Color.changealphaint(150, simplekml.Color.white)
                    imagens_embebidas_kmz.add(nome_arq_img_rep)

                    # Adicionar ponto para a repetidora (opcional, mas útil)
                    # Tenta extrair coords do nome do arquivo se possível (frágil)
                    try:
                        parts = nome_arq_img_rep.split('_')
                        lat_rep_str = parts[-2].replace('m','-').replace('_','.')
                        lon_rep_str = parts[-1].replace('.png','').replace('m','-').replace('_','.')
                        lat_rep, lon_rep = float(lat_rep_str), float(lon_rep_str)
                        pnt_rep = kml.newpoint(name=f"Repetidora ({nome_arq_img_rep.split('_')[1]})", coords=[(lon_rep, lat_rep)])
                        pnt_rep.style = torre_style # Reutiliza estilo da torre
                    except Exception: # fallback se nome não tem coords
                        lat_rep_centro = (bounds_rep[0] + bounds_rep[2]) / 2
                        lon_rep_centro = (bounds_rep[1] + bounds_rep[3]) / 2
                        pnt_rep = kml.newpoint(name=f"Repetidora ({nome_arq_img_rep.split('_')[1]})", coords=[(lon_rep_centro, lat_rep_centro)])
                        pnt_rep.style = torre_style


        # Salvar KML e criar KMZ
        os.makedirs(ARQUIVOS_DIR, exist_ok=True)
        caminho_kml_saida = os.path.join(ARQUIVOS_DIR, "estudo_irricontrol.kml")
        kml.save(caminho_kml_saida)

        nome_arquivo_kmz = f"EstudoIrricontrol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz"
        caminho_kmz_final = os.path.join(ARQUIVOS_DIR, nome_arquivo_kmz)

        with zipfile.ZipFile(caminho_kmz_final, 'w', zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(caminho_kml_saida, os.path.basename(caminho_kml_saida))
            
            # Adicionar imagens referenciadas ao KMZ
            for img_nome_relativo in imagens_embebidas_kmz:
                if img_nome_relativo: # Checa se não é None ou string vazia
                    caminho_img_abs = os.path.join(STATIC_IMAGENS_DIR, img_nome_relativo)
                    if os.path.exists(caminho_img_abs):
                        kmz_zip.write(caminho_img_abs, img_nome_relativo)
                    else:
                        print(f"Aviso: Imagem {img_nome_relativo} não encontrada para adicionar ao KMZ.")


        return FileResponse(caminho_kmz_final, media_type="application/vnd.google-earth.kmz", filename=nome_arquivo_kmz)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"❌ Erro em /exportar_kmz: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao exportar KMZ: {str(e)}")
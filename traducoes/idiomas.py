TRADUCOES = {
    "pt": {
        "erro_kmz": "Erro interno ao processar KMZ.",
        "carregando": "Processando...",
        "antena_nao_encontrada": "Antena não encontrada no KMZ.",
        "sucesso": "✅ Processamento concluído!",
        "erro_bounds": "Arquivo de bounds não encontrado.",
        "erro_imagem": "Imagem não encontrada.",
    },
    "en": {
        "erro_kmz": "Internal error processing KMZ.",
        "carregando": "Processing...",
        "antena_nao_encontrada": "Antenna not found in KMZ.",
        "sucesso": "✅ Process completed!",
        "erro_bounds": "Bounds file not found.",
        "erro_imagem": "Image not found.",
    },
    "es": {
        "erro_kmz": "Error interno al procesar KMZ.",
        "carregando": "Procesando...",
        "antena_nao_encontrada": "Antena no encontrada en KMZ.",
        "sucesso": "✅ ¡Proceso completado!",
        "erro_bounds": "Archivo de límites no encontrado.",
        "erro_imagem": "Imagen no encontrada.",
    },
    "de": {
        "erro_kmz": "Interner Fehler beim Verarbeiten von KMZ.",
        "carregando": "Wird verarbeitet...",
        "antena_nao_encontrada": "Antenne im KMZ nicht gefunden.",
        "sucesso": "✅ Vorgang abgeschlossen!",
        "erro_bounds": "Bounds-Datei nicht gefunden.",
        "erro_imagem": "Bild nicht gefunden.",
    },
    "ru": {
        "erro_kmz": "Внутренняя ошибка при обработке KMZ.",
        "carregando": "Обработка...",
        "antena_nao_encontrada": "Антенна не найдена в KMZ.",
        "sucesso": "✅ Обработка завершена!",
        "erro_bounds": "Файл границ не найден.",
        "erro_imagem": "Изображение не найдено.",
    },
}


def t(chave: str, lang: str = "pt") -> str:
    """
    Função para retornar o texto na língua escolhida.
    Se não achar a chave ou o idioma, retorna a própria chave.
    """
    return TRADUCOES.get(lang, TRADUCOES["en"]).get(chave, chave)

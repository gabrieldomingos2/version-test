// ===========================================
// event_listeners.js - Configuração de Eventos
// ===========================================

function setupEventListeners() {
    // --- Botões Superiores de Controle de Painéis e Visualização ---
    document.getElementById("toggle-painel")?.addEventListener("click", () => togglePainel("painel-dados"));
    document.getElementById("toggle-repetidoras")?.addEventListener("click", () => togglePainel("painel-repetidoras"));
    // REMOVIDO: document.getElementById("toggle-opacidade")?.addEventListener("click", () => togglePainel("painel-opacidade"));
    document.getElementById("btn-visada")?.addEventListener("click", toggleVisadaVisibility);
    document.getElementById("toggle-legenda")?.addEventListener("click", toggleLegendasVisibility);

    // --- Edição de Pivôs ---
    document.getElementById("editar-pivos")?.addEventListener("click", toggleEditMode);
    document.getElementById("desfazer-edicao")?.addEventListener("click", undoEdits);

    // --- Controles de Painéis Específicos ---
    // O listener para range-opacidade é mantido, pois o slider ainda existe, só mudou de lugar
    document.getElementById("range-opacidade")?.addEventListener("input", (e) => {
        // Certifica-se de que setOverlaysOpacity está definida (de map_handler.js)
        if (typeof setOverlaysOpacity === 'function') {
            setOverlaysOpacity(e.target.value);
        }
    });

    document.getElementById("fechar-painel-rep")?.addEventListener("click", () => {
        document.getElementById('painel-repetidora')?.classList.add('hidden');
        if (marcadorPosicionamento && map.hasLayer(marcadorPosicionamento)) {
            map.removeLayer(marcadorPosicionamento);
            marcadorPosicionamento = null;
        }
    });
    document.getElementById("confirmar-repetidora")?.addEventListener("click", () => {
        if (!coordenadaClicada) return mostrarMensagem("⚠️ Clique no mapa para definir a posição da repetidora.", "erro");
        const alturaAntena = parseFloat(document.getElementById("altura-antena-rep")?.value || 5);
        const alturaReceiver = parseFloat(document.getElementById("altura-receiver-rep")?.value || 3);
        // Certifica-se de que simulateRepeaterSignal está definida (de api_handler.js)
        if (typeof simulateRepeaterSignal === 'function') {
            simulateRepeaterSignal(coordenadaClicada.lat, coordenadaClicada.lng, alturaAntena, alturaReceiver);
        }
    });

    // --- Seletor de Template ---
    document.getElementById('template-modelo')?.addEventListener("change", (e) => {
        // Certifica-se de que updateSelectedTemplate está definida (de ui_handler.js)
        if (typeof updateSelectedTemplate === 'function') {
            updateSelectedTemplate(e.target.value);
        }
    });

    // --- Controles Laterais Principais ---
    const fileInput = document.getElementById('arquivo');
    const fileNameSpan = document.getElementById('nome-arquivo');
    fileInput?.addEventListener('change', () => {
        if(fileNameSpan && fileInput.files) fileNameSpan.textContent = fileInput.files[0]?.name || 'Escolher Arquivo';
    });

    document.getElementById('formulario')?.addEventListener('submit', (e) => {
        e.preventDefault();
        if (!fileInput || fileInput.files.length === 0) {
            return mostrarMensagem("Por favor, selecione um arquivo KMZ.", "erro");
        }
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        // Certifica-se de que processKmzFile está definida (de api_handler.js)
        if (typeof processKmzFile === 'function') {
            processKmzFile(formData);
        }
    });

    document.getElementById("simular-btn")?.addEventListener("click", simulateMainSignal);
    document.getElementById("btn-diagnostico")?.addEventListener("click", runFullDiagnosis);
    document.getElementById("exportar-btn")?.addEventListener("click", downloadKmz);
    document.getElementById("resetar-btn")?.addEventListener("click", () => {
        if (confirm("Tem certeza que deseja resetar toda a simulação?")) {
            if (typeof resetMap === 'function') resetMap();
            if (typeof resetUI === 'function') resetUI();
            mostrarMensagem("🔄 Aplicação resetada.", "info");
        }
    });

    // --- Eventos do Mapa ---
    // 'map' deve ser uma variável global inicializada em main.js
    if (map) {
        map.on("click", (e) => {
            if (modoEdicaoPivos) return; // modoEdicaoPivos é uma var global
            if (!antenaGlobal) return mostrarMensagem("⚠️ Carregue um KMZ antes de adicionar repetidoras.", "erro"); // antenaGlobal é var global

            coordenadaClicada = e.latlng; // coordenadaClicada é var global

            if (!marcadorPosicionamento) { // marcadorPosicionamento é var global
                // iconePosicionamento deve ser uma var global de main.js
                if (typeof iconePosicionamento !== 'undefined') {
                    marcadorPosicionamento = L.marker(coordenadaClicada, {
                        icon: iconePosicionamento,
                        interactive: false,
                    }).addTo(map);
                } else {
                    console.error("Ícone de posicionamento não definido.");
                }
            } else {
                marcadorPosicionamento.setLatLng(coordenadaClicada);
            }
            const painelRep = document.getElementById("painel-repetidora");
            if(painelRep) painelRep.classList.remove("hidden");
        });
    } else {
        console.error("Variável 'map' do Leaflet não está definida ao configurar eventos do mapa.");
    }
}
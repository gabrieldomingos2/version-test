// ===========================================
// event_listeners.js - Configuração de Eventos
// ===========================================

function setupEventListeners() {
    // --- Botões Superiores de Controle de Painéis e Visualização ---
    document.getElementById("toggle-painel")?.addEventListener("click", () => togglePainel("painel-dados"));
    document.getElementById("toggle-repetidoras")?.addEventListener("click", () => togglePainel("painel-repetidoras"));
    document.getElementById("toggle-opacidade")?.addEventListener("click", () => togglePainel("painel-opacidade"));
    document.getElementById("btn-visada")?.addEventListener("click", toggleVisadaVisibility);
    document.getElementById("toggle-legenda")?.addEventListener("click", toggleLegendasVisibility);

    // --- Edição de Pivôs ---
    document.getElementById("editar-pivos")?.addEventListener("click", toggleEditMode);
    document.getElementById("desfazer-edicao")?.addEventListener("click", undoEdits);

    // --- Controles de Painéis Específicos ---
    document.getElementById("range-opacidade")?.addEventListener("input", (e) => setOverlaysOpacity(e.target.value));
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
        simulateRepeaterSignal(coordenadaClicada.lat, coordenadaClicada.lng, alturaAntena, alturaReceiver);
    });

    // --- Seletor de Template ---
    document.getElementById('template-modelo')?.addEventListener("change", (e) => updateSelectedTemplate(e.target.value));

    // --- Controles Laterais Principais ---
    const fileInput = document.getElementById('arquivo');
    const fileNameSpan = document.getElementById('nome-arquivo');
    fileInput?.addEventListener('change', () => {
        if(fileNameSpan) fileNameSpan.textContent = fileInput.files[0]?.name || 'Escolher Arquivo';
    });

    document.getElementById('formulario')?.addEventListener('submit', (e) => {
        e.preventDefault();
        if (!fileInput || fileInput.files.length === 0) {
            return mostrarMensagem("Por favor, selecione um arquivo KMZ.", "erro");
        }
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        processKmzFile(formData);
    });

    document.getElementById("simular-btn")?.addEventListener("click", simulateMainSignal);
    document.getElementById("btn-diagnostico")?.addEventListener("click", runFullDiagnosis);
    document.getElementById("exportar-btn")?.addEventListener("click", downloadKmz); // Corrigido para não usar onclick
    document.getElementById("resetar-btn")?.addEventListener("click", () => {
        if (confirm("Tem certeza que deseja resetar toda a simulação?")) {
            resetMap();
            resetUI();
            mostrarMensagem("🔄 Aplicação resetada.", "info");
        }
    });

    // --- Eventos do Mapa ---
    map.on("click", (e) => {
        if (modoEdicaoPivos) return;
        if (!antenaGlobal) return mostrarMensagem("⚠️ Carregue um KMZ antes de adicionar repetidoras.", "erro");

        coordenadaClicada = e.latlng;

        if (!marcadorPosicionamento) {
            marcadorPosicionamento = L.marker(coordenadaClicada, {
                icon: iconePosicionamento, // Usa o ícone global definido em main.js
                interactive: false,
            }).addTo(map);
        } else {
            marcadorPosicionamento.setLatLng(coordenadaClicada);
        }
        // Mostra o painel de configuração da repetidora
        const painelRep = document.getElementById("painel-repetidora");
        if(painelRep) painelRep.classList.remove("hidden");
    });
}
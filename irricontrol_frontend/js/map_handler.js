// ===========================================
// map_handler.js - Funções do Mapa (Leaflet)
// ===========================================

function addAntenaMarker(antena) {
    if (marcadorAntena && map.hasLayer(marcadorAntena)) map.removeLayer(marcadorAntena);
    marcadorAntena = L.marker([antena.lat, antena.lon], { icon: antenaIcon })
        .addTo(map)
        .bindPopup(`<div class="popup-glass">📡 ${antena.nome || 'Antena Principal'}</div>`, { offset: [0, -30] });

    // Remove label antigo se existir
    if (antenaGlobal?.label && map.hasLayer(antenaGlobal.label)) map.removeLayer(antenaGlobal.label);
    antenaGlobal.label = addLabel(antena.lat, antena.lon, antena.nome || 'Antena', [35, -25]);
}

// Dentro de js/map_handler.js
function addPivoMarkers(pivosData) {
    clearPivoMarkers(); // Limpa marcadores e labels de pivôs existentes
    pivosData.forEach(pivo => {
        const cor = pivo.fora ? 'red' : 'green';
        const pos = posicoesEditadas[pivo.nome] || { lat: pivo.lat, lon: pivo.lon }; // Usa posição editada se houver, senão a original
        const marker = L.circleMarker([pos.lat, pos.lon], {
            radius: 6, color: cor, fillColor: cor, fillOpacity: 0.7,
            className: pivo.fora ? 'circulo-futurista' : ''
        }).addTo(map).bindPopup(`<div class="popup-glass">${pivo.fora ? '❌' : '✅'} ${pivo.nome}</div>`);

        marcadoresPivos.push(marker);
        pivotsMap[pivo.nome] = marker;
        // ADICIONE/CONFIRME ESTE LOG:
        console.log(`addPivoMarkers: Marcador adicionado/atualizado em pivotsMap com chave: '${pivo.nome}'`, marker); 
        marker.pivoLabel = addLabel(pos.lat, pos.lon, pivo.nome, [30, -15]);
    });
}

function addBombaMarkers(bombasData) {
    clearBombaMarkers();
    bombasData.forEach(bomba => {
        const marcadorBomba = L.marker([bomba.lat, bomba.lon], { icon: iconeBomba })
            .addTo(map)
            .bindPopup(`<div class="popup-glass">🚰 ${bomba.nome}</div>`);
        marcadoresBombas.push(marcadorBomba);
        marcadorBomba.bombaLabel = addLabel(bomba.lat, bomba.lon, bomba.nome, [40, -15]);
    });
}

function addCirculosKMZ(circulosData) {
    clearCirculosKMZ();
    circulosKMZ = circulosData.map(circulo =>
        L.polygon(circulo.coordenadas, {
            color: '#FF0000', weight: 4, opacity: 0.95, fillOpacity: 0,
        }).addTo(map)
    );
}

function addImageOverlay(url, boundsData) {
    const [south, west, north, east] = boundsData;
    const bounds = L.latLngBounds([[south, west], [north, east]]);
    const currentOpacity = parseFloat(document.getElementById('range-opacidade')?.value || 1);

    const overlay = L.imageOverlay(url + '?t=' + Date.now(), bounds, {
        opacity: currentOpacity,
        interactive: false // Overlays de imagem geralmente não precisam ser interativos
    }).addTo(map);
    return overlay;
}

function addLabel(lat, lon, text, anchor) {
    const labelMarker = L.marker([lat, lon], {
        icon: L.divIcon({
            className: 'label-pivo' + (legendasAtivas ? '' : ' hidden'),
            html: `<span>${text}</span>`,
            iconSize: [120, 20], // Aumentado para nomes mais longos
            iconAnchor: anchor
        }),
        interactive: false // Labels não precisam ser clicáveis
    }).addTo(map);
    marcadoresLegenda.push(labelMarker);
    return labelMarker;
}

function clearPivoMarkers() {
    marcadoresPivos.forEach(m => { if (map.hasLayer(m)) map.removeLayer(m); });
    Object.values(pivotsMap).forEach(m => {
        if (m.pivoLabel && map.hasLayer(m.pivoLabel)) map.removeLayer(m.pivoLabel);
        if (m.editMarker && map.hasLayer(m.editMarker)) map.removeLayer(m.editMarker);
        if (map.hasLayer(m)) map.removeLayer(m);
    });
    marcadoresPivos = [];
    pivotsMap = {};
}

function clearBombaMarkers() {
    marcadoresBombas.forEach(b => {
      if (b.bombaLabel && map.hasLayer(b.bombaLabel)) map.removeLayer(b.bombaLabel);
      if (map.hasLayer(b)) map.removeLayer(b);
    });
    marcadoresBombas = [];
}

function clearCirculosKMZ() {
    circulosKMZ.forEach(c => { if (map.hasLayer(c)) map.removeLayer(c); });
    circulosKMZ = [];
}

function clearAllOverlays() { // Renomeado para evitar conflito com a variável global
    overlaysVisiveis.forEach(o => { if (map.hasLayer(o)) map.removeLayer(o); });
    overlaysVisiveis = [];

    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay)) {
      map.removeLayer(antenaGlobal.overlay);
    }
    if (antenaGlobal) antenaGlobal.overlay = null;

    repetidoras.forEach(r => {
        if (r.overlay && map.hasLayer(r.overlay)) map.removeLayer(r.overlay);
        r.overlay = null;
    });
}

function clearAllLabels() { // Renomeado
    marcadoresLegenda.forEach(m => { if (map.hasLayer(m)) map.removeLayer(m); });
    marcadoresLegenda = [];

    if (antenaGlobal?.label && map.hasLayer(antenaGlobal.label)) map.removeLayer(antenaGlobal.label);
    if (antenaGlobal) antenaGlobal.label = null;

    repetidoras.forEach(r => {
        if (r.label && map.hasLayer(r.label)) map.removeLayer(r.label);
        r.label = null;
    });
}

function clearDiagnostico() {
    if (visadaLayerGroup) visadaLayerGroup.clearLayers();
    visadaVisivel = true;
    const btnVisada = document.getElementById("btn-visada");
    if (btnVisada) btnVisada.classList.remove("opacity-50");
}

function resetMap() {
    if (marcadorAntena && map.hasLayer(marcadorAntena)) map.removeLayer(marcadorAntena);
    if (marcadorPosicionamento && map.hasLayer(marcadorPosicionamento)) map.removeLayer(marcadorPosicionamento);

    clearPivoMarkers();
    clearBombaMarkers();
    clearCirculosKMZ();
    clearAllOverlays();
    clearAllLabels();
    clearDiagnostico();

    repetidoras.forEach(r => {
        if (r.marker && map.hasLayer(r.marker)) map.removeLayer(r.marker);
        // Labels de repetidoras são limpos em clearAllLabels
    });

    antenaGlobal = null;
    marcadorAntena = null;
    marcadorPosicionamento = null;
    // pivotsMap é limpo em clearPivoMarkers
    repetidoras = [];
    contadorRepetidoras = 0;
    idsDisponiveis = [];
    coordenadaClicada = null;
    posicoesEditadas = {};
    backupPosicoesPivos = {};
    // overlaysVisiveis é limpo em clearAllOverlays

    map.setView([-15, -55], 5);
}

// --- FUNÇÃO MODIFICADA COM LOGS ---
function updatePivosStatus(pivosData) {
    let foraCount = 0;
    pivosData.forEach(pivo => {
        const nomePadrao = pivo.nome.trim().toLowerCase();
        const marcador = pivotsMap[nomePadrao];
        const cor = pivo.fora ? 'red' : 'green';

        if (marcador) {
            marcador.setStyle({
                color: cor,
                fillColor: cor,
                fillOpacity: 0.7,
                className: pivo.fora ? 'circulo-futurista' : ''
            });

            marcador.bindPopup(
                `<div class="popup-glass">${pivo.fora ? '❌' : '✅'} ${pivo.nome}</div>`
            );

            if (pivo.fora) foraCount++;
        } else {
            console.warn(`Pivô "${pivo.nome}" não encontrado em pivotsMap`);
        }
    });
    document.getElementById("fora-cobertura").textContent = `Fora da cobertura: ${foraCount}`;
}

// --- FIM DA FUNÇÃO MODIFICADA ---

function toggleVisadaVisibility() {
    visadaVisivel = !visadaVisivel;
    visadaLayerGroup.eachLayer(layer => {
        const el = layer.getElement?.();
        const path = layer instanceof L.Path ? layer.getElement() : null; // Para polylines/polygons

        if (el) { // Para L.divIcon (labels)
            el.style.opacity = visadaVisivel ? 1 : 0;
        } else if (path) { // Para L.Polyline
             path.style.strokeOpacity = visadaVisivel ? 1 : 0; // Controla opacidade da linha
        }
    });
    document.getElementById("btn-visada").classList.toggle("opacity-50", !visadaVisivel);
}

function toggleLegendasVisibility() {
    legendasAtivas = !legendasAtivas;
    marcadoresLegenda.forEach(m => {
        const el = m.getElement?.();
        if (el) el.classList.toggle("hidden", !legendasAtivas);
    });
    document.getElementById("toggle-legenda").classList.toggle("opacity-50", !legendasAtivas);
}

function setOverlaysOpacity(value) {
    const opacityValue = parseFloat(value);
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay)) {
       antenaGlobal.overlay.setOpacity(opacityValue);
    }
    overlaysVisiveis.forEach(o => { // overlaysVisiveis deve conter apenas overlays de repetidoras agora
        if (o && map.hasLayer(o)) {
            o.setOpacity(opacityValue);
        }
    });
}

function drawDiagnostico(latlonAntena, latlonPivo, nomePivo, bloqueio) {
    const linha = L.polyline([latlonAntena, latlonPivo], {
        className: 'linha-futurista' // Aplica classe para animação inicial
    }).addTo(visadaLayerGroup);

    setTimeout(() => { // Após animação, muda estilo para algo mais permanente
        if (linha._path) { // Verifica se o elemento SVG da linha existe
            linha._path.classList.remove('linha-futurista');
            linha.setStyle({color: '#00ffff', weight: 2, dashArray: '5, 10'});
        }
    }, 2200); // Tempo da animação

    if (bloqueio) {
        const ponto = bloqueio; // {lat, lon, elev}
        const bloqueioIcon = L.divIcon({
            className: 'label-pivo', // Reutiliza estilo de label
            html: '⛰️ Bloqueio',
            iconSize: [70, 20],
            iconAnchor: [35, 10] // Centraliza
        });
        L.marker([ponto.lat, ponto.lon], { icon: bloqueioIcon })
            .addTo(visadaLayerGroup)
            .bindPopup(`
                <div class="popup-glass text-center leading-snug">
                ⛔ Elevação (${Math.round(ponto.elev)}m) acima da linha de visada<br>
                entre a antena e <strong>${nomePivo}</strong>
                </div>
            `);
    }
}

function toggleEditMode() {
    modoEdicaoPivos = !modoEdicaoPivos;
    const btnEditar = document.getElementById("editar-pivos");
    const btnDesfazer = document.getElementById("desfazer-edicao");

    btnEditar.textContent = modoEdicaoPivos ? "💾 Salvar Edições" : "✏️ Editar Pivôs";
    btnEditar.setAttribute('aria-label', modoEdicaoPivos ? "Salvar edições nas posições dos pivôs" : "Entrar no modo de edição de pivôs");
    btnEditar.classList.toggle('bg-yellow-600', modoEdicaoPivos);
    btnEditar.classList.toggle('hover:bg-yellow-700', modoEdicaoPivos);
    btnDesfazer.classList.toggle("hidden", !modoEdicaoPivos);

    if (modoEdicaoPivos) {
        backupPosicoesPivos = {}; // Limpa e refaz backup
        Object.entries(pivotsMap).forEach(([nome, marcador]) => {
            backupPosicoesPivos[nome] = marcador.getLatLng();
            if(marcador.pivoLabel) marcador.pivoLabel.setOpacity(0.5); // Diminui opacidade do label original
        });
    } else { // Saindo do modo de edição
         Object.entries(pivotsMap).forEach(([nome, marcador]) => {
            if(marcador.pivoLabel) marcador.pivoLabel.setOpacity(1);
        });
    }


    Object.entries(pivotsMap).forEach(([nome, marcador]) => {
        const labelOriginal = marcador.pivoLabel; // Label associado ao círculo

        if (modoEdicaoPivos) {
            marcador.setStyle({ color: 'yellow', fillColor: 'yellow' });
            const editMarker = L.marker(marcador.getLatLng(), {
                draggable: true,
                icon: L.divIcon({ className: 'label-pivo', html: `🎯`, iconSize: [20, 20], iconAnchor: [10, 10] })
            }).addTo(map);

            marcador.editMarker = editMarker; // Guarda referência

            editMarker.on("drag", (e) => { // Ao arrastar o alvo, move o label original junto
                if (labelOriginal) labelOriginal.setLatLng(e.target.getLatLng());
            });
            editMarker.on("dragend", (e) => {
                posicoesEditadas[nome] = e.target.getLatLng();
            });
            editMarker.on("contextmenu", (e) => {
                L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                if (confirm(`Tem certeza que deseja remover o pivô "${nome}"? Esta ação não pode ser desfeita aqui.`)) {
                    if (map.hasLayer(editMarker)) map.removeLayer(editMarker);
                    if (map.hasLayer(marcador)) map.removeLayer(marcador);
                    if (labelOriginal && map.hasLayer(labelOriginal)) map.removeLayer(labelOriginal);
                    delete pivotsMap[nome];
                    delete posicoesEditadas[nome];
                    delete backupPosicoesPivos[nome];
                    marcadoresPivos = marcadoresPivos.filter(m => m !== marcador);
                    marcadoresLegenda = marcadoresLegenda.filter(l => l !== labelOriginal);
                    mostrarMensagem(`🗑️ Pivô "${nome}" removido.`, "info");
                }
            });
        } else { // Saindo do modo de edição
            if (marcador.editMarker) {
                const novaPos = posicoesEditadas[nome] || marcador.editMarker.getLatLng(); // Usa posição salva ou a última do drag
                marcador.setLatLng(novaPos);
                if (labelOriginal) labelOriginal.setLatLng(novaPos);
                map.removeLayer(marcador.editMarker);
                delete marcador.editMarker;
            }
            // Restaura cor do pivô (requer reavaliação ou estado anterior)
             if (Object.keys(overlaysVisiveis).length > 0 || (antenaGlobal && antenaGlobal.overlay)) {
                reavaliarPivosViaAPI(); // Reavalia para definir cores corretas
            } else {
                marcador.setStyle({ color: 'red', fillColor: 'red' }); // Padrão para vermelho se não há simulação
            }
        }
    });

    if (!modoEdicaoPivos && Object.keys(posicoesEditadas).length > 0) {
        mostrarMensagem("💾 Edições salvas. Re-simule para aplicar.", "info");
        const btnSimular = document.getElementById("simular-btn");
        btnSimular.disabled = false;
        btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
    } else if (!modoEdicaoPivos) {
        mostrarMensagem("✏️ Edição finalizada.", "info");
    }
}

function undoEdits() {
    Object.entries(backupPosicoesPivos).forEach(([nome, posicaoOriginal]) => {
        const marcador = pivotsMap[nome];
        if (marcador?.editMarker) { // Se o marcador de edição ainda existe
            marcador.editMarker.setLatLng(posicaoOriginal);
            if(marcador.pivoLabel) marcador.pivoLabel.setLatLng(posicaoOriginal);
        }
        // Se o pivô original foi removido do mapa (deletado na edição), não podemos restaurá-lo aqui
        // A lógica de "undo" não recria pivôs deletados, apenas reverte posições dos existentes.
    });
    posicoesEditadas = {}; // Limpa as edições que seriam salvas
    mostrarMensagem("↩️ Edições revertidas para o estado anterior ao modo de edição.", "info");
}
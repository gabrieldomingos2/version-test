// ===========================================
// api_handler.js - Funções de API (Fetch)
// ===========================================

function formatCoordForFilename(coord) { // Renomeado para clareza
  return coord.toFixed(6).replace('.', '_').replace('-', 'm');
}

async function processKmzFile(formData) {
  mostrarLoader(true);
  try {
    const res = await fetch(`${API_BASE_URL}/kmz/processar_kmz`, { method: "POST", body: formData }); // ✅ CORRIGIDO
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status} ao processar KMZ` }));
        throw new Error(errorData.erro || `Erro HTTP ${res.status} ao processar KMZ`);
    }
    const data = await res.json();
    if (data.erro) throw new Error(data.erro);

    resetMap(); // Limpa mapa antes de carregar novo
    resetUI();  // Limpa UI

    antenaGlobal = data.antena;
    antenaGlobal.altura_receiver = antenaGlobal.altura_receiver || 3; // Garante valor padrão

    addAntenaMarker(antenaGlobal);
    addPivoMarkers(data.pivos.map(p => ({...p, fora: true}))); // Marca como fora inicialmente
    addBombaMarkers(data.bombas || []);
    if (data.ciclos) addCirculosKMZ(data.ciclos);

    // Garante que antenaGlobal e data.pivos são válidos antes de tentar fitBounds
    if (antenaGlobal && antenaGlobal.lat != null && antenaGlobal.lon != null && data.pivos && data.pivos.length > 0) {
        map.fitBounds(L.latLngBounds(data.pivos.map(p => [p.lat, p.lon])).extend(L.latLng(antenaGlobal.lat, antenaGlobal.lon)));
    } else if (antenaGlobal && antenaGlobal.lat != null && antenaGlobal.lon != null) {
        map.setView([antenaGlobal.lat, antenaGlobal.lon], 10); // Zoom padrão se não houver pivôs
    }


    mostrarMensagem("✅ KMZ carregado com sucesso.", "sucesso");

    document.getElementById("simular-btn").classList.remove("hidden");
    document.getElementById("painel-dados").classList.remove("hidden");
    document.getElementById("painel-dados").setAttribute('aria-hidden', 'false');
    document.getElementById("painel-repetidoras").classList.remove("hidden");
    document.getElementById("painel-repetidoras").setAttribute('aria-hidden', 'false');

    adicionarAntenaNoPainel(antenaGlobal);
    atualizarPainelDados(data.pivos, antenaGlobal, antenaGlobal.altura_receiver, data.bombas || []);

  } catch (error) {
    mostrarMensagem(`❌ Erro ao processar KMZ: ${error.message}`, "erro");
    console.error("Erro KMZ:", error);
  } finally {
    mostrarLoader(false);
  }
}

async function simulateMainSignal() {
  if (!antenaGlobal) return mostrarMensagem("⚠️ Carregue um KMZ primeiro.", "erro");
  mostrarLoader(true);

  const pivosParaSimulacao = Object.entries(pivotsMap).map(([nome, marcador]) => {
    const { lat, lng } = posicoesEditadas[nome] || marcador.getLatLng(); // Usa posição editada se houver
    return { nome, lat, lon: lng };
  });

  const payload = {
    lat: antenaGlobal.lat,
    lon: antenaGlobal.lon,
    altura: antenaGlobal.altura,
    altura_receiver: antenaGlobal.altura_receiver,
    nome: antenaGlobal.nome,
    pivos_atuais: pivosParaSimulacao,
    template: templateSelecionado
  };
  console.log("Payload para /simulation/simular_sinal:", JSON.stringify(payload, null, 2));


  try {
    const res = await fetch(`${API_BASE_URL}/simulation/simular_sinal`, { // ✅ CORRIGIDO
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status} na simulação principal` }));
        throw new Error(errorData.erro || `Erro HTTP ${res.status} na simulação principal`);
    }
    const data = await res.json();
    if (data.erro) throw new Error(data.erro);

    if (data.imagem_salva && data.bounds) {
      clearAllOverlays();
      antenaGlobal.overlay = addImageOverlay(data.imagem_salva, data.bounds);

      map.fitBounds(L.latLngBounds([[data.bounds[0], data.bounds[1]], [data.bounds[2], data.bounds[3]]]));

      updatePivosStatus(data.pivos);
      atualizarPainelDados(data.pivos, antenaGlobal, antenaGlobal.altura_receiver, data.bombas || []);
      mostrarMensagem("📡 Estudo de sinal principal concluído.", "sucesso");
      document.getElementById("btn-diagnostico").classList.remove("hidden");
      const btnSimular = document.getElementById("simular-btn");
      btnSimular.disabled = true;
      btnSimular.classList.add("opacity-50");
    } else {
      throw new Error("Resposta inválida da API de simulação.");
    }
  } catch (error) {
    mostrarMensagem(`❌ Erro na simulação principal: ${error.message}`, "erro");
    console.error("Erro Simulação Principal:", error);
  } finally {
    mostrarLoader(false);
  }
}

async function simulateRepeaterSignal(lat, lon, alturaAntena, alturaReceiver) {
    if (!antenaGlobal) return mostrarMensagem("⚠️ Carregue e simule a antena principal primeiro.", "erro");
    mostrarLoader(true);

    const pivosParaSimulacao = Object.entries(pivotsMap).map(([nome, marcador]) => {
        const { lat, lng } = posicoesEditadas[nome] || marcador.getLatLng();
        return { nome, lat, lon: lng };
    });

    const payload = {
        lat, lon,
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        pivos_atuais: pivosParaSimulacao,
        template: templateSelecionado
    };
    console.log("Payload para /simulation/simular_manual (repetidora):", JSON.stringify(payload, null, 2));

    try {
        const res = await fetch(`${API_BASE_URL}/simulation/simular_manual`, { // ✅ CORRIGIDO
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status} ao simular repetidora` }));
            throw new Error(errorData.erro || `Erro HTTP ${res.status} ao simular repetidora`);
        }
        const data = await res.json();
        if (data.erro) throw new Error(data.erro);

        if (data.imagem_salva && data.bounds) {
            const id = idsDisponiveis.length > 0 ? idsDisponiveis.shift() : ++contadorRepetidoras;
            const marker = L.marker([lat, lon], { icon: repetidoraIcon })
                .addTo(map)
                .bindPopup(`<div class="popup-glass">📡 Repetidora ${id}</div>`);
            const label = addLabel(lat, lon, `Repetidora ${id}`, [40, -25]);
            const overlay = addImageOverlay(data.imagem_salva, data.bounds);

            const repetidoraObj = { id, marker, overlay, altura: alturaAntena, altura_receiver: alturaReceiver, label };
            repetidoras.push(repetidoraObj);
            overlaysVisiveis.push(overlay);
            adicionarRepetidoraNoPainel(repetidoraObj);

            if (marcadorPosicionamento && map.hasLayer(marcadorPosicionamento)) {
                map.removeLayer(marcadorPosicionamento);
                marcadorPosicionamento = null;
            }
            document.getElementById("painel-repetidora").classList.add("hidden");
            await reavaliarPivosViaAPI();
            mostrarMensagem(`📡 Repetidora ${id} adicionada e simulada.`, "sucesso");
        } else {
             throw new Error("Resposta inválida da API de simulação de repetidora.");
        }
    } catch (error) {
        mostrarMensagem(`❌ Erro ao simular repetidora: ${error.message}`, "erro");
        console.error("Erro Simulação Repetidora:", error);
    } finally {
        mostrarLoader(false);
    }
}

async function reavaliarPivosViaAPI() {
    if (Object.keys(pivotsMap).length === 0) return;

    const pivosParaReavaliacao = Object.entries(pivotsMap).map(([nome, marcador]) => {
        const { lat, lng } = posicoesEditadas[nome] || marcador.getLatLng();
        return { nome, lat, lon: lng };
    });

    const activeOverlaysData = [];
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay)) {
        const b = antenaGlobal.overlay.getBounds();
        activeOverlaysData.push({
            imagem: antenaGlobal.overlay._url.split('?')[0],
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }
    overlaysVisiveis.forEach(overlay => {
        if (map.hasLayer(overlay)) {
            const b = overlay.getBounds();
            activeOverlaysData.push({
                imagem: overlay._url.split('?')[0],
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (pivosParaReavaliacao.length === 0 && activeOverlaysData.length === 0) {
        // Se não há pivôs ou overlays ativos, não há o que fazer,
        // mas talvez seja bom atualizar o status para garantir que todos sejam marcados como fora se não houver overlays.
        if (pivosParaReavaliacao.length > 0 && activeOverlaysData.length === 0) {
            updatePivosStatus(pivosParaReavaliacao.map(p => ({...p, fora: true })));
        }
        return;
    }


    try {
        const res = await fetch(`${API_BASE_URL}/simulation/reavaliar_pivos`, { // ✅ CORRIGIDO
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pivos: pivosParaReavaliacao, overlays: activeOverlaysData })
        });
        if (!res.ok) {
             const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status} ao reavaliar pivôs` }));
            throw new Error(errorData.erro || `Erro HTTP ${res.status} ao reavaliar pivôs`);
        }
        const data = await res.json();
        if (data.erro) throw new Error(data.erro);

        if (data.pivos) {
            updatePivosStatus(data.pivos);
        }
    } catch (error) {
        console.error("Erro ao reavaliar pivôs via API:", error);
        mostrarMensagem(`⚠️ Erro ao atualizar cobertura: ${error.message}`, "erro");
    }
}

async function fetchElevationProfile(pivoNome, marcadorPivo) {
    if (!antenaGlobal) return;
    const payload = {
        pontos: [
            [antenaGlobal.lat, antenaGlobal.lon],
            [marcadorPivo.getLatLng().lat, marcadorPivo.getLatLng().lng]
        ],
        altura_antena: antenaGlobal.altura ?? 15,
        altura_receiver: antenaGlobal.altura_receiver ?? 3
    };

    try {
        const res = await fetch(`${API_BASE_URL}/simulation/perfil_elevacao`, { // ✅ CORRIGIDO
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status} ao buscar perfil de elevação` }));
            throw new Error(errorData.erro || `Erro HTTP ${res.status} ao buscar perfil de elevação`);
        }
        const data = await res.json();
        if (data.erro) throw new Error(data.erro);

        drawDiagnostico(
            [antenaGlobal.lat, antenaGlobal.lon],
            [marcadorPivo.getLatLng().lat, marcadorPivo.getLatLng().lng],
            pivoNome,
            data.bloqueio
        );
    } catch (error) {
        console.error(`Erro no diagnóstico do pivô ${pivoNome}: ${error.message}`);
        mostrarMensagem(`Erro diagnóstico ${pivoNome}: ${error.message}`, "erro");
    }
}

async function runFullDiagnosis() {
    if (!antenaGlobal) return mostrarMensagem("⚠️ Carregue um KMZ e simule a antena principal primeiro!", "erro");
    if (Object.keys(pivotsMap).length === 0) return mostrarMensagem("⚠️ Nenhum pivô para diagnosticar.", "info");

    clearDiagnostico();
    mostrarLoader(true);
    let pivosDiagnosticados = 0;

    const promises = [];
    for (const [nome, marcador] of Object.entries(pivotsMap)) {
        if (marcador.options.fillColor === 'red') {
            promises.push(fetchElevationProfile(nome, marcador));
            pivosDiagnosticados++;
        }
    }

    if (pivosDiagnosticados === 0) {
        mostrarLoader(false);
        return mostrarMensagem("✅ Nenhum pivô fora de cobertura para diagnosticar.", "sucesso");
    }

    await Promise.allSettled(promises);

    mostrarLoader(false);
    mostrarMensagem(`🔍 Diagnóstico concluído para ${pivosDiagnosticados} pivôs.`, "sucesso");
}

function downloadKmz() {
    if (!antenaGlobal) {
        return mostrarMensagem("⚠️ Carregue um KMZ e rode o estudo da antena principal primeiro!", "erro");
    }

    let nomeImagemPrincipal = "";
    let nomeBoundsPrincipal = "";

    if (antenaGlobal.overlay && antenaGlobal.overlay._url) {
        const urlParts = antenaGlobal.overlay._url.split('?')[0].split('/');
        nomeImagemPrincipal = urlParts[urlParts.length - 1];
        nomeBoundsPrincipal = nomeImagemPrincipal.replace(".png", ".json");
    } else {
        mostrarMensagem("⚠️ Imagem da antena principal não encontrada. O KMZ pode não incluir a cobertura principal.", "info");
    }

    const params = new URLSearchParams();
    if (nomeImagemPrincipal) params.append("imagem", nomeImagemPrincipal);
    if (nomeBoundsPrincipal) params.append("bounds_file", nomeBoundsPrincipal);

    const url = `${API_BASE_URL}/kmz/exportar_kmz?${params.toString()}`; // ✅ CORRIGIDO
    window.open(url, '_blank');
}

async function fetchTemplates() {
    try {
        const res = await fetch(`${API_BASE_URL}/core/templates`); // ✅ CORRIGIDO
        if (!res.ok) throw new Error(`Falha ao buscar templates: ${res.status}`);
        const templates = await res.json();
        fillTemplateSelector(templates);
    } catch (err) {
        console.error("⚠️ Erro ao carregar templates:", err);
        mostrarMensagem("⚠️ Erro ao carregar templates. Usando valores padrão.", "erro");
        fillTemplateSelector(["Brazil V6", "Europe V6"]); // Fallback
    }
}
// ===========================================
// api_handler.js - Funções de API (Fetch)
// ===========================================

function formatCoordForFilename(coord) { // Renomeado para clareza
  return coord.toFixed(6).replace('.', '_').replace('-', 'm');
}

async function processKmzFile(formData) {
  mostrarLoader(true);
  try {
    const res = await fetch(`${API_BASE_URL}/processar_kmz`, { method: "POST", body: formData });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status}` }));
        throw new Error(errorData.erro || `Erro HTTP ${res.status}`);
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

    map.fitBounds(L.latLngBounds(data.pivos.map(p => [p.lat, p.lon])).extend(L.latLng(antenaGlobal.lat, antenaGlobal.lon)));
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
  console.log("Payload para /simular_sinal:", JSON.stringify(payload, null, 2));


  try {
    const res = await fetch(`${API_BASE_URL}/simular_sinal`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status}` }));
        throw new Error(errorData.erro || `Erro HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data.erro) throw new Error(data.erro);

    if (data.imagem_salva && data.bounds) {
      clearAllOverlays(); // Limpa overlays antigos (incluindo da antena principal)
      antenaGlobal.overlay = addImageOverlay(data.imagem_salva, data.bounds);
      // Não adiciona antenaGlobal.overlay a overlaysVisiveis aqui, pois setOverlaysOpacity já o trata.

      map.fitBounds(L.latLngBounds([[data.bounds[0], data.bounds[1]], [data.bounds[2], data.bounds[3]]]));
      // map.zoomOut(1); // Opcional, pode ser muito zoom out

      updatePivosStatus(data.pivos);
      atualizarPainelDados(data.pivos, antenaGlobal, antenaGlobal.altura_receiver, data.bombas || []);
      mostrarMensagem("📡 Estudo de sinal principal concluído.", "sucesso");
      document.getElementById("btn-diagnostico").classList.remove("hidden");
      const btnSimular = document.getElementById("simular-btn");
      btnSimular.disabled = true;
      btnSimular.classList.add("opacity-50"); // Tailwind para opacidade
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
    console.log("Payload para /simular_manual (repetidora):", JSON.stringify(payload, null, 2));

    try {
        const res = await fetch(`${API_BASE_URL}/simular_manual`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status}` }));
            throw new Error(errorData.erro || `Erro HTTP ${res.status}`);
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
            overlaysVisiveis.push(overlay); // Adiciona apenas overlay da repetidora aqui
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
    if (Object.keys(pivotsMap).length === 0) return; // Não faz nada se não há pivôs

    const pivosParaReavaliacao = Object.entries(pivotsMap).map(([nome, marcador]) => {
        const { lat, lng } = posicoesEditadas[nome] || marcador.getLatLng();
        return { nome, lat, lon: lng };
    });

    const activeOverlaysData = [];
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay)) {
        const b = antenaGlobal.overlay.getBounds();
        activeOverlaysData.push({
            imagem: antenaGlobal.overlay._url.split('?')[0], // Remove timestamp
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }
    overlaysVisiveis.forEach(overlay => { // overlaysVisiveis agora só tem repetidoras
        if (map.hasLayer(overlay)) {
            const b = overlay.getBounds();
            activeOverlaysData.push({
                imagem: overlay._url.split('?')[0], // Remove timestamp
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (pivosParaReavaliacao.length === 0) return; // Nada para reavaliar

    try {
        const res = await fetch(`${API_BASE_URL}/reavaliar_pivos`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pivos: pivosParaReavaliacao, overlays: activeOverlaysData })
        });
        if (!res.ok) {
             const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status}` }));
            throw new Error(errorData.erro || `Erro HTTP ${res.status}`);
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
        const res = await fetch(`${API_BASE_URL}/perfil_elevacao`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorData = await res.json().catch(() => ({ erro: `Erro HTTP ${res.status}` }));
            throw new Error(errorData.erro || `Erro HTTP ${res.status}`);
        }
        const data = await res.json();
        if (data.erro) throw new Error(data.erro);

        drawDiagnostico(
            [antenaGlobal.lat, antenaGlobal.lon],
            [marcadorPivo.getLatLng().lat, marcadorPivo.getLatLng().lng],
            pivoNome,
            data.bloqueio // Backend retorna null se não houver bloqueio
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
        if (marcador.options.fillColor === 'red') { // Diagnosticar apenas os vermelhos
            promises.push(fetchElevationProfile(nome, marcador));
            pivosDiagnosticados++;
        }
    }

    if (pivosDiagnosticados === 0) {
        mostrarLoader(false);
        return mostrarMensagem("✅ Nenhum pivô fora de cobertura para diagnosticar.", "sucesso");
    }

    await Promise.allSettled(promises); // Espera todas as promises, mesmo que algumas falhem

    mostrarLoader(false);
    mostrarMensagem(`🔍 Diagnóstico concluído para ${pivosDiagnosticados} pivôs.`, "sucesso");
}

function downloadKmz() {
    if (!antenaGlobal) {
        return mostrarMensagem("⚠️ Carregue um KMZ e rode o estudo da antena principal primeiro!", "erro");
    }

    // Tenta pegar o nome da imagem e bounds da antena principal se ela tiver sido simulada
    let nomeImagemPrincipal = "";
    let nomeBoundsPrincipal = "";

    if (antenaGlobal.overlay && antenaGlobal.overlay._url) {
        const urlParts = antenaGlobal.overlay._url.split('?')[0].split('/');
        nomeImagemPrincipal = urlParts[urlParts.length - 1];
        nomeBoundsPrincipal = nomeImagemPrincipal.replace(".png", ".json");
    } else {
        // Fallback se a antena principal não foi simulada ou não tem overlay
        // (pode acontecer se o usuário tentar exportar antes da simulação completa)
        // Neste caso, o KMZ não terá o overlay da antena principal.
        mostrarMensagem("⚠️ Imagem da antena principal não encontrada. O KMZ pode não incluir a cobertura principal.", "info");
    }

    const params = new URLSearchParams();
    if (nomeImagemPrincipal) params.append("imagem", nomeImagemPrincipal);
    if (nomeBoundsPrincipal) params.append("bounds_file", nomeBoundsPrincipal);

    const url = `${API_BASE_URL}/exportar_kmz?${params.toString()}`;
    window.open(url, '_blank');
}

async function fetchTemplates() {
    try {
        const res = await fetch(`${API_BASE_URL}/templates`);
        if (!res.ok) throw new Error(`Falha ao buscar templates: ${res.status}`);
        const templates = await res.json();
        fillTemplateSelector(templates);
    } catch (err) {
        console.error("⚠️ Erro ao carregar templates:", err);
        mostrarMensagem("⚠️ Erro ao carregar templates. Usando valores padrão.", "erro");
        fillTemplateSelector(["Brazil_V6", "Europe_V6_XR"]); // Fallback
    }
}
// ===========================================
// ui_handler.js - Funções de Interface (UI)
// ===========================================

function mostrarMensagem(texto, tipo = 'sucesso') {
    const msgElement = document.getElementById('mensagem');
    if (!msgElement) return;
    msgElement.textContent = texto;
    msgElement.className = `fixed bottom-16 left-1/2 transform -translate-x-1/2 text-white px-6 py-3 rounded-lg text-center font-semibold z-[10001] shadow-lg ${tipo === 'sucesso' ? 'bg-green-600' : tipo === 'erro' ? 'bg-red-600' : 'bg-blue-500'}`;
    // Força reflow para reiniciar animação se houver
    msgElement.style.display = 'none';
    msgElement.offsetHeight; // Trigger reflow
    msgElement.style.display = '';

    setTimeout(() => { msgElement.classList.add('hidden'); }, 4000);
}

function mostrarLoader(ativo) {
    const loaderElement = document.getElementById('loader');
    if (!loaderElement) return;
    loaderElement.classList.toggle('hidden', !ativo);
    loaderElement.setAttribute('aria-hidden', String(!ativo));
}

function togglePainel(id) {
    const painel = document.getElementById(id);
    if (!painel) return;
    const isHidden = painel.classList.toggle("hidden");
    painel.setAttribute('aria-hidden', String(isHidden));
}

function adicionarAntenaNoPainel(antena) {
    const painelRepetidoras = document.getElementById("lista-repetidoras");
    if (!painelRepetidoras) return;

    const oldItem = document.getElementById("antena-item");
    if (oldItem) oldItem.remove();

    const itemAntena = document.createElement("div");
    itemAntena.className = "flex justify-between items-center bg-gray-700/50 px-3 py-2 rounded-md border border-white/10";
    itemAntena.id = "antena-item";

    const labelAnt = document.createElement("label");
    labelAnt.textContent = antena.nome || "Antena Principal";
    labelAnt.className = "text-white/90 flex-1 truncate pr-2 text-sm";
    labelAnt.htmlFor = "toggle-antena-vis";

    const toggleAntena = document.createElement("input");
    toggleAntena.type = "checkbox";
    toggleAntena.checked = true;
    toggleAntena.className = "form-checkbox text-green-500 cursor-pointer";
    toggleAntena.id = "toggle-antena-vis";

    toggleAntena.addEventListener("change", () => {
        const isChecked = toggleAntena.checked;
        if (marcadorAntena) {
            isChecked ? marcadorAntena.addTo(map) : map.removeLayer(marcadorAntena);
        }
        if (antenaGlobal.overlay) { // Adicionado "?." para segurança
            isChecked ? map.addLayer(antenaGlobal.overlay) : map.removeLayer(antenaGlobal.overlay);
            if (isChecked && !overlaysVisiveis.includes(antenaGlobal.overlay)) {
                overlaysVisiveis.push(antenaGlobal.overlay);
            } else if (!isChecked) {
                overlaysVisiveis = overlaysVisiveis.filter(o => o !== antenaGlobal.overlay);
            }
        }
        if (antenaGlobal.label) { // Adicionado "?."
            isChecked ? antenaGlobal.label.addTo(map) : map.removeLayer(antenaGlobal.label);
        }
        reavaliarPivosViaAPI();
    });

    itemAntena.appendChild(labelAnt);
    itemAntena.appendChild(toggleAntena);
    painelRepetidoras.prepend(itemAntena);
}

function adicionarRepetidoraNoPainel(repetidora) {
    const container = document.getElementById("lista-repetidoras");
    if (!container) return;

    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-800/50 px-3 py-2 rounded-md border border-white/10";
    item.id = `rep-item-${repetidora.id}`;

    const label = document.createElement("label");
    label.textContent = `Repetidora ${repetidora.id}`;
    label.className = "text-white/90 flex-1 truncate pr-2 text-sm";
    label.htmlFor = `toggle-rep-${repetidora.id}`;

    const controls = document.createElement("div");
    controls.className = "flex gap-3 items-center";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "form-checkbox text-green-500 cursor-pointer";
    checkbox.id = `toggle-rep-${repetidora.id}`;

    checkbox.addEventListener("change", () => {
        const isChecked = checkbox.checked;
        if (repetidora.marker) {
            isChecked ? repetidora.marker.addTo(map) : map.removeLayer(repetidora.marker);
        }
        if (repetidora.overlay) {
            isChecked ? map.addLayer(repetidora.overlay) : map.removeLayer(repetidora.overlay);
            if (isChecked && !overlaysVisiveis.includes(repetidora.overlay)) {
                overlaysVisiveis.push(repetidora.overlay);
            } else if (!isChecked) {
                overlaysVisiveis = overlaysVisiveis.filter(o => o !== repetidora.overlay);
            }
        }
        if (repetidora.label) {
            isChecked ? repetidora.label.addTo(map) : map.removeLayer(repetidora.label);
        }
        reavaliarPivosViaAPI();
    });

    const removerBtn = document.createElement("button");
    removerBtn.innerHTML = "❌";
    removerBtn.className = "text-xl text-red-500 hover:text-red-700 transition focus:outline-none";
    removerBtn.setAttribute("aria-label", `Remover Repetidora ${repetidora.id}`);

    removerBtn.addEventListener("click", () => {
        if (repetidora.marker && map.hasLayer(repetidora.marker)) map.removeLayer(repetidora.marker);
        if (repetidora.overlay && map.hasLayer(repetidora.overlay)) {
            map.removeLayer(repetidora.overlay);
            overlaysVisiveis = overlaysVisiveis.filter(o => o !== repetidora.overlay);
        }
        if (repetidora.label && map.hasLayer(repetidora.label)) map.removeLayer(repetidora.label);

        container.removeChild(item);
        idsDisponiveis.push(repetidora.id);
        idsDisponiveis.sort((a, b) => a - b);
        repetidoras = repetidoras.filter(r => r.id !== repetidora.id);

        reavaliarPivosViaAPI();
        atualizarPainelInfoRepetidoras();
    });

    controls.appendChild(checkbox);
    controls.appendChild(removerBtn);
    item.appendChild(label);
    item.appendChild(controls);
    container.appendChild(item);
    atualizarPainelInfoRepetidoras();
}

function atualizarPainelDados(pivos, antena, receiverAltura, bombas) {
    document.getElementById("total-pivos").textContent = `Pivôs: ${pivos ? pivos.length : 0}`;
    document.getElementById("fora-cobertura").textContent = `Fora da cobertura: ${pivos ? pivos.filter(p => p.fora).length : 0}`;
    document.getElementById("altura-antena-info").textContent = `Antena principal: ${antena?.altura || '--'} m`;
    document.getElementById("altura-receiver-info").textContent = `Receiver: ${receiverAltura || '--'} m`;
    document.getElementById("total-repetidoras").textContent = `Total Repetidoras: ${repetidoras.length}`;
    document.getElementById("template-info").textContent = `🌐 Template: ${templateSelecionado || '--'}`;

    const bombasElemento = document.getElementById("total-bombas");
    if (bombas && bombas.length > 0) {
        bombasElemento.textContent = `Casas de bomba: ${bombas.length}`;
        bombasElemento.classList.remove("hidden");
    } else {
        bombasElemento.classList.add("hidden");
    }
}

function atualizarPainelInfoRepetidoras() {
    document.getElementById("total-repetidoras").textContent = `Total Repetidoras: ${repetidoras.length}`;
}

function resetUI() {
    document.getElementById("lista-repetidoras").innerHTML = "";

    ['painel-repetidora', 'painel-dados', 'painel-repetidoras', 'painel-opacidade'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.classList.add("hidden");
            el.setAttribute('aria-hidden', 'true');
        }
    });

    const btnSimular = document.getElementById("simular-btn");
    btnSimular.classList.add("hidden");
    btnSimular.disabled = false;
    btnSimular.classList.remove("opacity-50", "cursor-not-allowed");

    document.getElementById("btn-diagnostico").classList.add("hidden");
    document.getElementById('nome-arquivo').textContent = 'Escolher Arquivo';
    document.getElementById('arquivo').value = '';
    document.getElementById('range-opacidade').value = 1;

    modoEdicaoPivos = false;
    const btnEditar = document.getElementById("editar-pivos");
    btnEditar.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
    btnEditar.textContent = "✏️ Edit Pivots";
    btnEditar.setAttribute('aria-label', "Entrar ou Sair do Modo de Edição de Pivôs");
    document.getElementById("desfazer-edicao").classList.add("hidden");

    Object.values(pivotsMap).forEach(m => {
        if (m.editMarker && map.hasLayer(m.editMarker)) {
            map.removeLayer(m.editMarker);
        }
        delete m.editMarker; // Garante remoção da referência
    });
}

function fillTemplateSelector(templates) {
    const select = document.getElementById('template-modelo');
    if(!select) return;
    select.innerHTML = '';
    templates.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t; // Assume que 't' é o ID do template
        opt.textContent = t.includes("Brazil") ? "🇧🇷 " + t :
                          t.includes("Europe") ? "🇪🇺 " + t :
                          "🌐 " + t;
        select.appendChild(opt);
    });

    templateSelecionado = localStorage.getItem('templateSelecionado') || (templates.length > 0 ? templates[0] : "");
    select.value = templateSelecionado;
    if (document.getElementById("template-info")) {
        document.getElementById("template-info").textContent = `🌐 Template: ${templateSelecionado || '--'}`;
    }
}

function updateSelectedTemplate(value) {
    templateSelecionado = value;
    localStorage.setItem('templateSelecionado', templateSelecionado);
    if (document.getElementById("template-info")) {
        document.getElementById("template-info").textContent = `🌐 Template: ${templateSelecionado || '--'}`;
    }
    if (antenaGlobal) {
        const btnSimular = document.getElementById("simular-btn");
        btnSimular.disabled = false;
        btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
        mostrarMensagem("Template alterado. Rode o estudo novamente para aplicar as mudanças.", "info");
    }
}
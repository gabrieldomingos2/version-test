// ===========================================
// main.js - Inicialização e Variáveis Globais
// ===========================================

// --- Constantes ---
const API_BASE_URL = "https://irricontrol-test.onrender.com";
// As URLs abaixo não serão mais usadas para os ícones principais,
// mas podem ser mantidas se usadas para outros fins.
const IMG_BASE_URL = `${API_BASE_URL}/static/imagens`;
const ICON_TOWER_URL = `${API_BASE_URL}/icone-torre`;

// --- Variáveis Globais de Estado da Aplicação ---
let map;
let visadaLayerGroup; // Grupo para linhas e marcadores de diagnóstico de visada
let overlaysVisiveis = []; // Armazena ImageOverlays ativos para controle de opacidade e reavaliação
let antenaGlobal = null;   // Objeto com dados da antena principal {lat, lon, altura, nome, overlay, label, etc.}
let pivotsMap = {};       // Objeto para mapear nome_pivo -> L.CircleMarker
let repetidoras = [];       // Array de objetos de repetidoras {id, marker, overlay, label, altura, altura_receiver}
let posicoesEditadas = {}; // { nomePivo: L.latLng } - Armazena posições alteradas no modo de edição
let backupPosicoesPivos = {}; // { nomePivo: L.latLng } - Backup para desfazer edições

// --- Variáveis Globais de UI e Controle ---
let marcadorAntena = null;       // L.Marker da antena principal
let marcadorPosicionamento = null; // L.Marker temporário para posicionar nova repetidora
let coordenadaClicada = null;   // L.LatLng do último clique no mapa para repetidora
let templateSelecionado = "";
let contadorRepetidoras = 0;   // Para gerar IDs únicos para repetidoras
let idsDisponiveis = [];     // Para reutilizar IDs de repetidoras removidas
let visadaVisivel = true;
let legendasAtivas = true;
let modoEdicaoPivos = false;

// Coleções de marcadores para fácil limpeza
let marcadoresPivos = [];     // Array de L.CircleMarker dos pivôs
let circulosKMZ = [];         // Array de L.Polygon dos círculos originais do KMZ
let marcadoresBombas = [];     // Array de L.Marker das bombas
let marcadoresLegenda = [];   // Array de L.Marker para todos os rótulos de texto no mapa

// --- Ícones Globais (Leaflet) ---
let antenaIcon, iconeBomba, iconePosicionamento, repetidoraIcon; // Serão definidos no DOMContentLoaded

// --- Inicialização da Aplicação ---
document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM Carregado. Inicializando Simulador Irricontrol...");

    // ========================================================================
    // Define Ícones após Leaflet estar disponível - USANDO PASTA LOCAL
    // ========================================================================
    antenaIcon = L.icon({
        iconUrl: 'assets/images/cloudrf.png',
        iconSize:     [28, 28],          
        iconAnchor:   [14, 28],          
        popupAnchor:  [0, -35]             
    });

    iconeBomba = L.icon({
        iconUrl: 'assets/images/homegardenbusiness.png', 
        iconSize:     [28, 28],             
        iconAnchor:   [14, 28],
        popupAnchor:  [0, -14]
    });

    iconePosicionamento = L.icon({
        iconUrl: 'assets/images/cloudrf.png', 
        iconSize:     [28, 28],            
        iconAnchor:   [14, 28],            
        className: 'leaflet-marker-icon-transparent'
    });

    repetidoraIcon = L.icon({
        iconUrl: 'assets/images/cloudrf.png', 
        iconSize:     [28, 28],            
        iconAnchor:   [14, 28],            
        popupAnchor:  [0, -35]              
    });
    // ========================================================================

    // 1. Inicializa o mapa
    map = L.map('map', {
        zoomControl: false // Controle de zoom padrão desativado
    }).setView([-15, -55], 5);

    L.control.zoom({ position: 'bottomright' }).addTo(map); // Adiciona controle de zoom em outra posição

    // 2. Adiciona camada de satélite
    L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: 'Map data &copy; Google, Imagens &copy; Maxar Technologies, CNES/Airbus'
    }).addTo(map);

    // 3. Cria grupo de camadas para linhas de visada
    visadaLayerGroup = L.layerGroup().addTo(map);

    // 4. Busca os templates de rádio
    fetchTemplates(); // (de api_handler.js)

    // 5. Configura todos os event listeners da aplicação
    setupEventListeners(); // (de event_listeners.js)

    console.log("Aplicação Irricontrol Simulador inicializada com sucesso.");
});
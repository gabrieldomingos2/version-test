projeto-irricontrol/
│
├── backend/
│   ├── main.py               # 🚀 API FastAPI principal
│   ├── requirements.txt      # 📦 Dependências Python
│   ├── utils/                # 🧠 Funções auxiliares
│   │   ├── __init__.py
│   │   ├── parser.py         # KMZ, KML parser e manipulação de dados geográficos
│   │   ├── signal.py         # Lógica de simulação de sinal (CloudRF)
│   │   ├── image_analysis.py # Análise de imagem para cobertura
│   │   ├── kmz_export.py     # Geração de KMZ final
│   ├── services/             # 🚀 Integrações externas
│   │   ├── __init__.py
│   │   ├── cloudrf_service.py # API CloudRF
│   │   └── elevation_service.py # API OpenTopoData ou Mapbox Terrain
│   ├── static/               # 🌐 Arquivos estáticos
│   │   ├── imagens/
│   │   └── contorno_fazenda.json
│   └── arquivos/             # 📦 Uploads temporários (KMZ, bounds, etc)
│
├── frontend/
│   ├── index.html            # 🌍 Página principal
│   ├── assets/               # 🎨 CSS, imagens, ícones
│   ├── js/                   # 🤖 Scripts separados (mapa, UI, lógica)
│   └── styles/               # 🎨 Arquivos CSS customizados
│
├── README.md                 # 📝 Documentação básica
└── .gitignore                # 🔥 Ignorar pastas como /__pycache__/ e /arquivos/

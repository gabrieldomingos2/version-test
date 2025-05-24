from pydantic import BaseModel
from typing import List, Optional, Any

class PivoData(BaseModel):
    nome: str
    lat: float
    lon: float
    fora: Optional[bool] = None # 'fora' é mais um status de resultado

class PivoInput(BaseModel): # Apenas dados que o frontend envia para identificar
    nome: str
    lat: float
    lon: float

class AntenaBase(BaseModel):
    lat: float
    lon: float
    altura: int
    nome: Optional[str] = None
    altura_receiver: Optional[int] = 3

class SimularSinalRequest(AntenaBase):
    template: str
    pivos_atuais: List[PivoInput]

class SimularManualRequest(BaseModel):
    lat: float
    lon: float
    altura: Optional[int] = 15
    altura_receiver: Optional[int] = 3
    template: str
    pivos_atuais: List[PivoInput]

class OverlayData(BaseModel):
    imagem: str
    bounds: List[float] # [sul, oeste, norte, leste]

class ReavaliarPivosRequest(BaseModel):
    pivos: List[PivoInput]
    overlays: List[OverlayData]

class PontoPerfil(BaseModel):
    lat: float
    lon: float

class PerfilElevacaoRequest(BaseModel):
    pontos: List[List[float]] # Lista de [lat, lon]
    altura_antena: Optional[int] = 15
    altura_receiver: Optional[int] = 3

# --- Modelos de Resposta (Opcional, mas bom para consistência) ---
class AntenaResponse(AntenaBase):
    pass # Pode adicionar mais campos específicos de resposta

class ProcessKmzResponse(BaseModel):
    antena: AntenaResponse
    pivos: List[PivoData]
    ciclos: List[Any] # Pode ser mais específico se a estrutura do ciclo for conhecida
    bombas: List[PivoData] # Reutiliza PivoData se a estrutura for similar

class SimulationResponse(BaseModel):
    imagem_salva: str
    bounds: List[float]
    status: str
    pivos: List[PivoData]

class BloqueioData(BaseModel):
    lat: float
    lon: float
    elev: float

class PerfilElevacaoResponse(BaseModel):
    bloqueio: Optional[BloqueioData] = None
    elevacao: List[float]

class ReavaliarPivosResponse(BaseModel):
    pivos: List[PivoData]
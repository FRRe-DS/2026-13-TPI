from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EstadoOferta(str, Enum):
    pendiente = "pendiente"
    aceptada = "aceptada"
    rechazada = "rechazada"
    vencida = "vencida"
    cancelada = "cancelada"


class OfertaCreate(BaseModel):
    solicitud_id: str
    conductor_id: str
    tiempo_expiracion_seg: Optional[int] = 30


class OfertaResponse(BaseModel):
    oferta_id: UUID
    solicitud_id: UUID
    conductor_id: UUID
    estado: EstadoOferta
    creada_en: datetime
    vence_en: datetime
    respondida_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ItemOfertaM3(BaseModel):
    oferta_id: UUID
    conductor_id: UUID


class LoteOfertasM3(BaseModel):
    solicitud_id: UUID
    origen_latitud: float = Field(..., ge=-90, le=90)
    origen_longitud: float = Field(..., ge=-180, le=180)
    destino_latitud: float = Field(..., ge=-90, le=90)
    destino_longitud: float = Field(..., ge=-180, le=180)
    tipo_vehiculo: str
    ofertas: List[ItemOfertaM3] = Field(..., min_length=1)
    vence_en: datetime


class RespuestaOfertaRequest(BaseModel):
    """Cuerpo enviado por M3 al responder una oferta (RF-5.5)."""
    solicitud_id: str
    oferta_id: str
    conductor_id: str
    respuesta: Literal["aceptado", "rechazado"]


class ResultadoRespuestaOferta(BaseModel):
    """repetida=true si la misma respuesta ya estaba registrada."""
    repetida: bool

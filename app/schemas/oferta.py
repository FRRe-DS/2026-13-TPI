from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class EstadoOferta(str, Enum):
    pendiente = "pendiente"
    aceptada = "aceptada"
    rechazada = "rechazada"
    vencida = "vencida"
    cancelada = "cancelada"


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
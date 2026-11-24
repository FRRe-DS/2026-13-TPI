from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CandidatoM4(BaseModel):
    """Un conductor de la lista que devuelve M4."""
    conductor_id: UUID
    distancia_origen_km: float = Field(ge=0)
    eta_retiro_minutos: Optional[int] = Field(default=None, ge=0)
    tipo_vehiculo: Literal["AUTO", "MOTO"]


class ResultadoBusquedaM4(BaseModel):
    """Respuesta completa de GET /api/v1/conductores/cercanos de M4."""
    conductores: list[CandidatoM4]
    radio_aplicado_km: float = Field(gt=0)
    generado_en: datetime


class RespuestaBusqueda(BaseModel):
    """Lo que devuelve M5 al iniciar la búsqueda de candidatos (RF-5.3)."""
    mensaje: str
    solicitud_id: UUID
    estado: str
    radio_aplicado_km: float
    generado_en: datetime
    conductores: list[CandidatoM4]
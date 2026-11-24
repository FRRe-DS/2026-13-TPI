from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict


class OfertaCreate(BaseModel):
    id_solicitud: str
    conductor_id: str
    tiempo_expiracion_seg: Optional[int] = 30


class OfertaResponse(BaseModel):
    id_oferta: str
    id_solicitud: str
    conductor_id: str
    fecha_envio: datetime
    fecha_expiracion: datetime
    estado: str

    model_config = ConfigDict(from_attributes=True)


class RespuestaOfertaRequest(BaseModel):
    cliente_id: str
    accion: Literal["ACEPTAR", "RECHAZAR"]


class RespuestaOfertaResponse(BaseModel):
    id_oferta: str
    id_solicitud: str
    estado_oferta: str
    estado_solicitud: str
    mensaje: str

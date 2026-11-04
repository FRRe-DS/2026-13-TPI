from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict
from uuid import UUID


# Crear oferta
class OfertaCreate(BaseModel):
    id_solicitud: str
    conductor_id: str
    tiempo_expiracion_seg: Optional[int] = 30  # Tiempo por defecto para el vencimiento (30s)

# Respuesta de la API
class OfertaResponse(BaseModel):
    id_oferta: str
    id_solicitud: str
    conductor_id: str
    fecha_envio: datetime
    fecha_expiracion: datetime
    estado: str

    model_config = ConfigDict(from_attributes=True)

# Responder una oferta (RF-5.5)
class RespuestaOferta(BaseModel):
    cliente_id: UUID
    accion: Literal["ACEPTAR", "RECHAZAR"]
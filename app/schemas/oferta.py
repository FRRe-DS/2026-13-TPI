from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

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

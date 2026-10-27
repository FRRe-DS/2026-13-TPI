
from uuid import UUID
from typing import Literal
from fastapi import FastAPI, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.solicitud import Solicitud
from app.routers import oferta


app = FastAPI(
    title="API M5 - Solicitud y Despacho",
    description="Servicio de solicitudes y asignacion de conductores",
    version="0.1.0"
)

app.include_router(oferta.router)

class SolicitudViaje(BaseModel):
    cliente_id: UUID
    origen_latitud: float = Field(ge=-90, le=90)
    origen_longitud: float = Field(ge=-180, le=180)
    destino_latitud: float = Field(ge=-90, le=90)
    destino_longitud: float = Field(ge=-180, le=180)
    tipo_vehiculo: Literal["AUTO", "MOTO"]


class RespuestaSolicitud(BaseModel):
    mensaje: str
    solicitud_id: UUID
    estado: str


@app.get("/")
def inicio():
    return {"mensaje": "API del Grupo 13 - Modulo M5"}


@app.post("/solicitudes", status_code=201, response_model=RespuestaSolicitud)
def crear_solicitud(
    solicitud: SolicitudViaje,
    db: Session = Depends(obtener_db)
):
    nueva_solicitud = Solicitud(
        cliente_id=str(solicitud.cliente_id),
        origen_latitud=solicitud.origen_latitud,
        origen_longitud=solicitud.origen_longitud,
        destino_latitud=solicitud.destino_latitud,
        destino_longitud=solicitud.destino_longitud,
        tipo_vehiculo=solicitud.tipo_vehiculo
    )

    db.add(nueva_solicitud)
    db.commit()
    db.refresh(nueva_solicitud)

    return {
        "mensaje": "Solicitud creada correctamente",
        "solicitud_id": nueva_solicitud.solicitud_id,
        "estado": nueva_solicitud.estado
    }

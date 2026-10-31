from uuid import UUID
from typing import Literal, Optional
from fastapi import FastAPI, Depends, HTTPException, status
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


class CancelarSolicitudRequest(BaseModel):
    cliente_id: UUID


class RespuestaCancelacion(BaseModel):
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


@app.post(
    "/solicitudes/{solicitud_id}/cancelar",
    status_code=status.HTTP_200_OK,
    response_model=RespuestaCancelacion,
    summary="Cancelación previa de solicitud (RF-5.7)"
)
def cancelar_solicitud_previa(
    solicitud_id: UUID,
    datos: Optional[CancelarSolicitudRequest] = None,
    db: Session = Depends(obtener_db)
):
    solicitud = db.query(Solicitud).filter(Solicitud.solicitud_id == str(solicitud_id)).first()

    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La solicitud no fue encontrada."
        )

    if datos and str(solicitud.cliente_id) != str(datos.cliente_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para cancelar una solicitud que no le pertenece."
        )

    if solicitud.estado != "PENDIENTE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede cancelar la solicitud porque su estado actual es '{solicitud.estado}'."
        )

    solicitud.estado = "CANCELADA"
    db.commit()
    db.refresh(solicitud)

    return {
        "mensaje": "Solicitud cancelada correctamente antes de la asignación",
        "solicitud_id": solicitud.solicitud_id,
        "estado": solicitud.estado
    }

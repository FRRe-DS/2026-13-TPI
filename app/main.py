from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.solicitud import Solicitud


app = FastAPI(
    title="API M5 - Solicitud y Despacho",
    description="Servicio de solicitudes y asignacion de conductores",
    version="0.1.0"
)


class SolicitudViaje(BaseModel):
    origen: str
    destino: str
    tipo_vehiculo: str


@app.get("/")
def inicio():
    return {"mensaje": "API del Grupo 13 - Modulo M5"}


@app.post("/solicitudes", status_code=201)
def crear_solicitud(
    solicitud: SolicitudViaje,
    db: Session = Depends(obtener_db)
):
    nueva_solicitud = Solicitud(
        origen=solicitud.origen,
        destino=solicitud.destino,
        tipo_vehiculo=solicitud.tipo_vehiculo
    )

    db.add(nueva_solicitud)
    db.commit()
    db.refresh(nueva_solicitud)

    return {
        "mensaje": "Solicitud creada correctamente",
        "id": nueva_solicitud.id,
        "estado": nueva_solicitud.estado
    }
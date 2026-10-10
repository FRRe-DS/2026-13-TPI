from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="API M5 - Solicitud y Despacho",
    description="Servicio de solicitudes y asignacion de conductores",
    version="0.1.0"
)


class SolicitudViaje(BaseModel):
    origen: str
    destino: str
    tipo_vehiculo: str


solicitudes = []


@app.get("/")
def inicio():
    return {"mensaje": "API del Grupo 13 - Modulo M5"}


@app.get("/solicitudes")
def listar_solicitudes():
    return {"solicitudes": solicitudes}


@app.post("/solicitudes")
def crear_solicitud(solicitud: SolicitudViaje):
    solicitudes.append(solicitud)
    return {
        "mensaje": "Solicitud creada correctamente",
        "solicitud": solicitud
    }
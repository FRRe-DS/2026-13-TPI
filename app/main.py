import asyncio
import hashlib
import logging

from contextlib import asynccontextmanager, suppress
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import (
    FastAPI, Depends, HTTPException, status,
    Header, Response, BackgroundTasks
)
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.observability.metricas import registrar_solicitud_creada

from app.database import obtener_db, SessionLocal
from app.models.solicitud import Solicitud
from app.models.evento_notificacion import EventoNotificacion
from app.routers import oferta, busqueda

# Autenticación y autorización mediante M1 (Keycloak).
from app.auth import validar_cliente, obtener_token_servicio
from app.services.clientes import validar_estado_cuenta
from app.services.estimacion import consultar_distancia, consultar_tarifa
from app.services.busqueda import iniciar_busqueda
from app.services.notificaciones import (
    construir_evento_viaje_solicitado,
    procesar_evento,
    reintentar_eventos_pendientes
)

logger = logging.getLogger(__name__)


async def tarea_notificaciones():

    while True:
        # Espera 60 segundos entre cada revisión.
        await asyncio.sleep(60)

        # Procesa los eventos sin bloquear la API.
        await asyncio.to_thread(
            reintentar_eventos_pendientes
        )
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Inicia la tarea cuando arranca la API.
    tarea = asyncio.create_task(tarea_notificaciones())

    try:
        yield

    finally:
        # Detiene la tarea periódica al cerrar la API.
        tarea.cancel()

        with suppress(asyncio.CancelledError):
            await tarea
app = FastAPI(
    title="API M5 - Solicitud y Despacho",
    description="Servicio de solicitudes y asignacion de conductores",
    version="0.1.0",
    lifespan=lifespan
)
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", tags=["Salud"])
def health_check():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Salud"])
def readiness_check(db: Session = Depends(obtener_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible",
        )

app.include_router(oferta.router, prefix="/api/v1")
app.include_router(busqueda.router, prefix="/api/v1")


class SolicitudViaje(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_id: Optional[UUID] = None
    origen_latitud: float = Field(ge=-90, le=90)
    origen_longitud: float = Field(ge=-180, le=180)
    destino_latitud: float = Field(ge=-90, le=90)
    destino_longitud: float = Field(ge=-180, le=180)
    tipo_vehiculo: Literal["AUTO", "MOTO"]


class RespuestaSolicitud(BaseModel):
    solicitud_id: UUID
    cliente_id: UUID
    origen_latitud: float
    origen_longitud: float
    destino_latitud: float
    destino_longitud: float
    tipo_vehiculo: Literal["AUTO", "MOTO"]
    estado: str
    creada_en: datetime


class CancelarSolicitudRequest(BaseModel):
    cliente_id: UUID


class RespuestaCancelacion(BaseModel):
    mensaje: str
    solicitud_id: UUID
    estado: str


# ──esquema RF-5.2 (Solicitud desde reserva) ───────────────

class SolicitudDesdeReservaRequest(BaseModel):
    reserva_id: UUID
    cliente_id: UUID
    origen_latitud: float = Field(ge=-90, le=90)
    origen_longitud: float = Field(ge=-180, le=180)
    destino_latitud: float = Field(ge=-90, le=90)
    destino_longitud: float = Field(ge=-180, le=180)
    tipo_vehiculo: Literal["AUTO", "MOTO"]


class RespuestaSolicitudReserva(BaseModel):
    mensaje: str
    solicitud_id: UUID
    reserva_id: UUID
    estado: str

# ── rutas de la API ─────────────────────────────────────────────────────────
@app.get("/")
def inicio():
    return {"mensaje": "API del Grupo 13 - Modulo M5"}

# ── Estimación de tarifa RF-5.1 ──────────────────

@app.post("/api/v1/solicitudes/estimacion")
def estimar_solicitud(
    solicitud: SolicitudViaje,
    cliente: dict = Depends(validar_cliente)
):
    # Obtiene las credenciales de servicio de M5.
    token = obtener_token_servicio()

    # Consulta la distancia y duración del trayecto a M4.
    ruta = consultar_distancia(
        solicitud.origen_latitud,
        solicitud.origen_longitud,
        solicitud.destino_latitud,
        solicitud.destino_longitud,
        token
    )

    # Solicita a M7 el cálculo de la tarifa.
    tarifa = consultar_tarifa(
        solicitud.tipo_vehiculo,
        ruta["distancia_estimada_km"],
        ruta["eta_minutos"],
        token
    )

    # Devuelve la estimación al cliente.
    return {
        "moneda": tarifa["moneda"],
        "total_estimado": tarifa["desglose"]["total"],
        "distancia_estimada_km": ruta["distancia_estimada_km"],
        "duracion_estimada_min": ruta["eta_minutos"]
    }

def ejecutar_busqueda(solicitud_id: str):

    # Utiliza una sesión independiente para la búsqueda.
    db = SessionLocal()

    try:
        iniciar_busqueda(db, solicitud_id)

    except Exception:
        db.rollback()

        logger.exception(
            "Error al iniciar la búsqueda de la solicitud %s",
            solicitud_id
        )

    finally:
        db.close()

# ── endpoint RF-5.1 ───────────────────────────────────────────
@app.post("/api/v1/solicitudes", status_code=201, response_model=RespuestaSolicitud)
def crear_solicitud(
    solicitud: SolicitudViaje,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(
        None, alias="Idempotency-Key"
    ),
    db: Session = Depends(obtener_db),
    cliente: dict = Depends(validar_cliente)
):
    # Valida la clave de idempotencia según el contrato.
    if (
        not idempotency_key
        or not idempotency_key.strip()
        or len(idempotency_key) > 128
    ):
        raise HTTPException(400, "Idempotency-Key inválida o ausente")
    # Obtiene la identidad del cliente autenticado mediante M1.
    try:
        cliente_id = UUID(cliente["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, "Identificador del cliente inválido")

    if solicitud.cliente_id is not None and solicitud.cliente_id != cliente_id:
        raise HTTPException(403, "El identificador no coincide con el token")

    # Genera una huella de los datos originales de la petición.
    request_hash = hashlib.sha256(
        solicitud.model_dump_json(exclude_unset=True).encode("utf-8")
    ).hexdigest()

    # Busca una solicitud previa del mismo cliente con la misma clave.
    def buscar_existente():
        return db.query(Solicitud).filter(
            Solicitud.cliente_id == str(cliente_id),
            Solicitud.idempotency_key == idempotency_key
        ).first()

    existente = buscar_existente()

    if existente:
        # La misma clave no puede utilizarse con datos diferentes.
        if existente.request_hash != request_hash:
            raise HTTPException(409, "Clave de idempotencia reutilizada con otros datos")

        response.status_code = 200
        resultado = existente

    else:
        # Valida el estado de cuenta del cliente mediante M2.
        token_servicio = obtener_token_servicio()
        validar_estado_cuenta(cliente_id, token_servicio)

        nueva_solicitud = Solicitud(
            cliente_id=str(cliente_id),
            cliente_email=cliente.get("email"),
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            origen_latitud=solicitud.origen_latitud,
            origen_longitud=solicitud.origen_longitud,
            destino_latitud=solicitud.destino_latitud,
            destino_longitud=solicitud.destino_longitud,
            tipo_vehiculo=solicitud.tipo_vehiculo
        )

        db.add(nueva_solicitud)

        try:
            # Genera el identificador de la solicitud sin confirmar
            # todavía la transacción.
            db.flush()

            # Construye el evento que posteriormente recibirá M8.
            cuerpo_evento = construir_evento_viaje_solicitado(
                nueva_solicitud
            )

            # Registra el evento pendiente de envío.
            evento = EventoNotificacion(
                evento_id=cuerpo_evento["eventoId"],
                solicitud_id=nueva_solicitud.solicitud_id,
                tipo="VIAJE_SOLICITADO",
                cuerpo=cuerpo_evento,
                estado="PENDIENTE"
            )

            db.add(evento)

            db.commit()

            # Métrica DevOps: contabilizar únicamente solicitudes nuevas persistidas.
            registrar_solicitud_creada(
                origen="inmediata",
                tipo_vehiculo=solicitud.tipo_vehiculo,
            )

            db.refresh(nueva_solicitud)
            resultado = nueva_solicitud

        except IntegrityError:
            # Evita duplicados cuando llegan peticiones simultáneas.
            db.rollback()
            existente = buscar_existente()

            if existente is None:
                raise

            if existente.request_hash != request_hash:
                raise HTTPException(409, "Clave de idempotencia reutilizada con otros datos")

            response.status_code = 200
            resultado = existente
        else:
            try:
                procesar_evento(db, evento, token_servicio)

            except Exception:
                db.rollback()
                logger.exception(
                    "Error al procesar la notificación de M8"
                )

            # Inicia RF-5.3 después de responder al cliente.
            background_tasks.add_task(
                ejecutar_busqueda,
                str(nueva_solicitud.solicitud_id)
            )

    # Indica la ubicación de la solicitud registrada.
    response.headers["Location"] = (
        f"/api/v1/solicitudes/{resultado.solicitud_id}"
    )

    return {
        "solicitud_id": resultado.solicitud_id,
        "cliente_id": resultado.cliente_id,
        "origen_latitud": resultado.origen_latitud,
        "origen_longitud": resultado.origen_longitud,
        "destino_latitud": resultado.destino_latitud,
        "destino_longitud": resultado.destino_longitud,
        "tipo_vehiculo": resultado.tipo_vehiculo,
        "estado": resultado.estado.lower(),
        "creada_en": resultado.fecha_creacion
    }
 
# ── endpoint RF-5.2 ───────────────────────────────────────────

@app.post(
    "/api/v1/solicitudes/desde-reserva",
    status_code=status.HTTP_201_CREATED,
    response_model=RespuestaSolicitudReserva,
    summary="Solicitud de viaje proveniente de reserva (RF-5.2)"
)
def crear_solicitud_desde_reserva(
    datos: SolicitudDesdeReservaRequest,
    db: Session = Depends(obtener_db)
):
    reserva_id_str = str(datos.reserva_id)

# 1. Control de Idempotencia: Verificar si esta reserva ya generó una solicitud (acuerdo M9)
    solicitud_existente = db.query(Solicitud).filter(Solicitud.reserva_id == reserva_id_str).first()
    if solicitud_existente:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "mensaje": "Solicitud recuperada previamente",
                "solicitud_id": str(solicitud_existente.solicitud_id),
                "reserva_id": str(solicitud_existente.reserva_id),
                "estado": solicitud_existente.estado
            }
        )

    # 2. Registrar la nueva solicitud
    nueva_solicitud = Solicitud(
        reserva_id=reserva_id_str,
        cliente_id=str(datos.cliente_id),
        origen_latitud=datos.origen_latitud,
        origen_longitud=datos.origen_longitud,
        destino_latitud=datos.destino_latitud,
        destino_longitud=datos.destino_longitud,
        tipo_vehiculo=datos.tipo_vehiculo,
        estado="PENDIENTE"
    )

    db.add(nueva_solicitud)
    db.commit()
    db.refresh(nueva_solicitud)

    return {
        "mensaje": "Solicitud desde reserva creada correctamente",
        "solicitud_id": nueva_solicitud.solicitud_id,
        "reserva_id": nueva_solicitud.reserva_id,
        "estado": nueva_solicitud.estado
    }

@app.post(
    "/api/v1/solicitudes/{solicitud_id}/cancelar",
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

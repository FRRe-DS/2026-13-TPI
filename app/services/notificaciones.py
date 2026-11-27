import os
import httpx
import logging
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from sqlalchemy.orm import Session
from app.models.evento_notificacion import EventoNotificacion
from app.database import SessionLocal
from app.auth import obtener_token_servicio

# Dirección del módulo de notificaciones.
M8_URL = os.getenv("M8_URL")
logger = logging.getLogger(__name__)
MAX_INTENTOS = 3

def enviar_evento(evento: dict, token_servicio: str):

    if not M8_URL:
        logger.warning("M8 no configurado")
        return "NO_CONFIGURADO", 0

    try:
        respuesta = httpx.post(
            f"{M8_URL}/api/v1/eventos",
            json=evento,
            headers={
                "Authorization": f"Bearer {token_servicio}"
            },
            timeout=5.0
        )

        if respuesta.status_code == 202:
            return "ENVIADO", 0

        if respuesta.status_code in (500, 503):

            espera = 60

            # Respeta el tiempo de espera indicado por M8.
            retry_after = respuesta.headers.get("Retry-After")

            if retry_after:
                try:
                    espera = max(60, int(retry_after))

                except ValueError:
                    try:
                        fecha = parsedate_to_datetime(retry_after)
                        segundos = (
                            fecha - datetime.now(timezone.utc)
                        ).total_seconds()

                        espera = max(60, segundos)

                    except (ValueError, TypeError, OverflowError):
                        pass

            return "REINTENTAR", espera

        logger.error(
            "Error al notificar a M8. Código: %s",
            respuesta.status_code
        )

        return "ERROR", 0

    except httpx.RequestError as error:
        logger.error("Error de comunicación con M8: %s", error)
        return "REINTENTAR", 60

def construir_evento_viaje_solicitado(solicitud):

    # Genera un identificador único para el evento.
    evento_id = str(uuid4())

    # Identifica al cliente que recibirá la notificación.
    destinatario = {
        "usuarioId": solicitud.cliente_id,
        "rol": "CLIENTE",
        "canalesPreferidos": ["PUSH", "EMAIL"]
    }

    # Incorpora el correo obtenido del JWT, si está disponible.
    if solicitud.cliente_email:
        destinatario["email"] = solicitud.cliente_email

    # Construye el mensaje que será enviado a M8.
    return {
        "eventoId": evento_id,
        "tipo": "VIAJE_SOLICITADO",
        "origen": "M5",
        "ocurridoEn": datetime.now(timezone.utc).isoformat(),
        "solicitudId": solicitud.solicitud_id,
        "destinatarios": [destinatario],
        "detalle": {
            "tipoVehiculo": solicitud.tipo_vehiculo
        }
    }

def procesar_evento(
    db: Session,
    evento: EventoNotificacion,
    token_servicio: str
):
    # Bloquea el registro para evitar procesamientos concurrentes.
    evento = db.query(EventoNotificacion).filter(
        EventoNotificacion.evento_id == evento.evento_id
    ).populate_existing().with_for_update().first()

    if evento is None or evento.estado != "PENDIENTE":
        db.rollback()
        return

    ahora = datetime.now(timezone.utc)

    # Verifica si corresponde realizar el siguiente intento.
    if evento.proximo_intento is not None:
        fecha = evento.proximo_intento

        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)

        if fecha > ahora:
            db.rollback()
            return

    resultado, espera = enviar_evento(
        evento.cuerpo,
        token_servicio
    )
    # Si M8 todavía no está configurado, no consume intentos.
    if resultado == "NO_CONFIGURADO":
        db.rollback()
        return
    evento.intentos += 1
    evento.proximo_intento = None

    if resultado == "ENVIADO":
        evento.estado = "ENVIADO"
        evento.fecha_envio = datetime.now(timezone.utc)

    elif resultado == "REINTENTAR" and evento.intentos < MAX_INTENTOS:
        evento.estado = "PENDIENTE"
        evento.proximo_intento = (
            datetime.now(timezone.utc) + timedelta(seconds=espera)
        )

    else:
        evento.estado = "ERROR"

        logger.error(
            "ERROR_INTEGRACION: evento %s",
            evento.evento_id
        )

    db.commit()

def reintentar_eventos_pendientes():

    db = SessionLocal()

    try:
        # Recupera los eventos pendientes de envío.
        eventos = db.query(EventoNotificacion).filter(
            EventoNotificacion.estado == "PENDIENTE",
            (
                EventoNotificacion.proximo_intento.is_(None)
                | (
                    EventoNotificacion.proximo_intento
                    <= datetime.now(timezone.utc)
                )
            )
        ).all()

        if not eventos:
            return

        # Obtiene un token de servicio actualizado.
        token_servicio = obtener_token_servicio()

        # Reutiliza la función de procesamiento existente.
        for evento in eventos:
            procesar_evento(db, evento, token_servicio)

    except Exception:
        db.rollback()
        logger.exception(
            "Error al reintentar notificaciones pendientes"
        )

    finally:
        db.close()
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.despacho import HistorialDespacho
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud

ESTADO_SIN_CONDUCTOR = "SIN_CONDUCTOR"
MOTIVOS_VALIDOS = ("SIN_CANDIDATOS", "BUSQUEDA_VENCIDA")

# Duración del período de búsqueda (RF-5.8). Configurable por variable de entorno.
BUSQUEDA_TIMEOUT_SEG_DEFECTO = 120


def obtener_timeout_busqueda_seg() -> int:
    """Lee BUSQUEDA_TIMEOUT_SEG; si falta o es inválida, usa el valor por defecto."""
    try:
        valor = int(os.getenv("BUSQUEDA_TIMEOUT_SEG", BUSQUEDA_TIMEOUT_SEG_DEFECTO))
    except ValueError:
        return BUSQUEDA_TIMEOUT_SEG_DEFECTO
    return valor if valor > 0 else BUSQUEDA_TIMEOUT_SEG_DEFECTO


def marcar_sin_conductor(db: Session, solicitud_id: str, motivo: str) -> dict:
    """RF-5.8: pasa una solicitud PENDIENTE a SIN_CONDUCTOR, una sola vez.

    - Si ya estaba en SIN_CONDUCTOR, no duplica nada y lo informa (idempotente).
    - Si estaba ACEPTADA o CANCELADA, responde 409.
    """
    ahora = datetime.now(timezone.utc)

    # 1) Cambio atómico: solo gana si sigue PENDIENTE y sin conductor
    r_solicitud = db.execute(
        update(Solicitud)
        .where(
            Solicitud.solicitud_id == solicitud_id,
            Solicitud.estado == "PENDIENTE",
            Solicitud.conductor_id.is_(None),
        )
        .values(estado=ESTADO_SIN_CONDUCTOR)
        .execution_options(synchronize_session=False)
    )

    if r_solicitud.rowcount != 1:
        db.rollback()
        estado_actual = db.scalar(
            select(Solicitud.estado).where(Solicitud.solicitud_id == solicitud_id)
        )
        if estado_actual is None:
            raise HTTPException(status_code=404, detail="La solicitud no fue encontrada.")
        if estado_actual == ESTADO_SIN_CONDUCTOR:
            return {
                "solicitud_id": solicitud_id,
                "estado": ESTADO_SIN_CONDUCTOR,
                "motivo": motivo,
                "mensaje": "La solicitud ya estaba registrada como sin conductor.",
                "ya_registrada": True,
            }
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede marcar la solicitud como sin conductor "
                f"porque su estado actual es '{estado_actual}'."
            ),
        )

    # 2) Las ofertas que seguían pendientes ya no tienen sentido: se vencen
    db.execute(
        update(Oferta)
        .where(Oferta.id_solicitud == solicitud_id, Oferta.estado == "PENDIENTE")
        .values(estado="EXPIRADA")
        .execution_options(synchronize_session=False)
    )

    # 3) Historial (RF-5.9), en la misma transacción
    db.add(HistorialDespacho(
        id_solicitud=solicitud_id,
        estado_anterior="PENDIENTE",
        estado_nuevo=ESTADO_SIN_CONDUCTOR,
        fecha_cambio=ahora,
    ))
    db.commit()

    return {
        "solicitud_id": solicitud_id,
        "estado": ESTADO_SIN_CONDUCTOR,
        "motivo": motivo,
        "mensaje": "No hay conductores disponibles para la solicitud.",
        "ya_registrada": False,
    }


def vencer_busquedas(db: Session, timeout_seg: int | None = None) -> dict:
    """RF-5.8: marca SIN_CONDUCTOR las solicitudes PENDIENTE cuyo período de búsqueda venció."""
    timeout = timeout_seg if timeout_seg is not None else obtener_timeout_busqueda_seg()
    limite = datetime.now(timezone.utc) - timedelta(seconds=timeout)

    ids_vencidas = db.scalars(
        select(Solicitud.solicitud_id).where(
            Solicitud.estado == "PENDIENTE",
            Solicitud.conductor_id.is_(None),
            Solicitud.fecha_creacion < limite,
        )
    ).all()

    marcadas = []
    for solicitud_id in ids_vencidas:
        try:
            resultado = marcar_sin_conductor(db, solicitud_id, "BUSQUEDA_VENCIDA")
        except HTTPException:
            # Cambió de estado mientras procesábamos (por ejemplo, la aceptaron): se omite
            continue
        if not resultado["ya_registrada"]:
            marcadas.append(solicitud_id)

    return {
        "timeout_seg": timeout,
        "cantidad": len(marcadas),
        "solicitudes": marcadas,
    }

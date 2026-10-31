from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.despacho import HistorialDespacho
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud


def asignar_conductor(db: Session, id_oferta: str) -> dict:
    """RF-5.6: asigna el conductor de la oferta a la solicitud, una sola vez."""
    ahora = datetime.now(timezone.utc)

    oferta = db.get(Oferta, id_oferta)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

    id_solicitud = oferta.id_solicitud
    conductor_id = oferta.conductor_id

    # 1) Competir por la solicitud: solo una transacción puede ganar
    r_solicitud = db.execute(
        update(Solicitud)
        .where(
            Solicitud.solicitud_id == id_solicitud,
            Solicitud.estado == "PENDIENTE",
            Solicitud.conductor_id.is_(None),
        )
        .values(conductor_id=conductor_id, estado="ACEPTADA", fecha_asignacion=ahora)
        .execution_options(synchronize_session=False)
    )
    if r_solicitud.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="La solicitud ya fue asignada a otro conductor"
        )

    # 2) La oferta debe seguir pendiente y vigente
    r_oferta = db.execute(
        update(Oferta)
        .where(
            Oferta.id_oferta == id_oferta,
            Oferta.estado == "PENDIENTE",
            Oferta.fecha_expiracion > ahora,
        )
        .values(estado="ACEPTADA")
        .execution_options(synchronize_session=False)
    )
    if r_oferta.rowcount != 1:
        db.rollback()  # deshace también la asignación del paso 1
        raise HTTPException(status_code=409, detail="La oferta ya fue respondida o expiró")

    # 3) Historial, en la misma transacción
    db.add(HistorialDespacho(
        id_solicitud=id_solicitud,
        estado_anterior="PENDIENTE",
        estado_nuevo="ACEPTADA",
        fecha_cambio=ahora,
    ))
    db.commit()

    return {
        "id_oferta": id_oferta,
        "id_solicitud": id_solicitud,
        "estado_oferta": "ACEPTADA",
        "estado_solicitud": "ACEPTADA",
        "mensaje": "Oferta aceptada y conductor asignado",
    }


def rechazar_oferta(db: Session, id_oferta: str) -> dict:
    """RF-5.5: rechaza una oferta pendiente y vigente. La solicitud no cambia."""
    ahora = datetime.now(timezone.utc)

    oferta = db.get(Oferta, id_oferta)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    id_solicitud = oferta.id_solicitud

    r_oferta = db.execute(
        update(Oferta)
        .where(
            Oferta.id_oferta == id_oferta,
            Oferta.estado == "PENDIENTE",
            Oferta.fecha_expiracion > ahora,
        )
        .values(estado="RECHAZADA")
        .execution_options(synchronize_session=False)
    )
    if r_oferta.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="La oferta ya fue respondida o expiró")

    estado_solicitud = db.scalar(
        select(Solicitud.estado).where(Solicitud.solicitud_id == id_solicitud)
    )
    db.add(HistorialDespacho(
        id_solicitud=id_solicitud,
        estado_anterior=estado_solicitud,
        estado_nuevo=estado_solicitud,
        fecha_cambio=ahora,
    ))
    db.commit()

    return {
        "id_oferta": id_oferta,
        "id_solicitud": id_solicitud,
        "estado_oferta": "RECHAZADA",
        "estado_solicitud": estado_solicitud,
        "mensaje": "Oferta rechazada",
    }
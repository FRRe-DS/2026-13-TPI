from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.despacho import HistorialDespacho
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud
from app.schemas.oferta import RespuestaOfertaRequest, ResultadoRespuestaOferta

# Estados de solicitud en los que se puede responder una oferta
_ESTADOS_ACTIVOS = {"pendiente", "buscando"}


def _aware(dt: datetime) -> datetime:
    """Garantiza datetime timezone-aware. SQLite devuelve naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def procesar_respuesta_oferta(
    db: Session,
    oferta_id: str,
    body: RespuestaOfertaRequest,
) -> ResultadoRespuestaOferta:
    """RF-5.5: registra la respuesta (aceptado/rechazado) enviada por M3.

    Orden de evaluación según contrato:
    1. Idempotencia (misma respuesta ya registrada) → 200 repetida=true
    2. Conflicto de solicitud → 409
    3. Vigencia de oferta → 410
    4. Procesar aceptación o rechazo
    """
    ahora = datetime.now(timezone.utc)

    # ── 1. Buscar oferta ────────────────────────────────────────────────────
    oferta = db.get(Oferta, oferta_id)
    if oferta is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "urn:m5:problema:no-encontrada",
                "title": "No encontrada",
                "status": 404,
                "codigo": "oferta_no_encontrada",
            },
        )

    # ── 2. Validar que solicitud_id del cuerpo coincide con la oferta ───────
    if oferta.solicitud_id != body.solicitud_id:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "urn:m5:problema:datos-invalidos",
                "title": "Datos inválidos",
                "status": 400,
                "detail": "solicitud_id no corresponde a la oferta indicada",
            },
        )

    # ── 3. Validar que el conductor es el destinatario ──────────────────────
    if oferta.conductor_id != body.conductor_id:
        raise HTTPException(
            status_code=403,
            detail={
                "type": "urn:m5:problema:no-autorizado",
                "title": "No autorizado",
                "status": 403,
                "detail": "El conductor no es el destinatario de la oferta",
            },
        )

    # ── 4. Idempotencia: misma respuesta ya registrada ──────────────────────
    if oferta.estado in ("aceptada", "rechazada"):
        respuesta_previa = "aceptado" if oferta.estado == "aceptada" else "rechazado"
        if respuesta_previa == body.respuesta:
            return ResultadoRespuestaOferta(repetida=True)

    # ── 5. Conflicto de solicitud (409 antes de 410) ────────────────────────
    solicitud = db.get(Solicitud, oferta.solicitud_id)
    if solicitud.estado not in _ESTADOS_ACTIVOS:
        if oferta.estado == "aceptada" and body.respuesta == "rechazado":
            motivo = "ya_aceptada"
        elif solicitud.estado == "asignada":
            motivo = "ya_asignada"
        elif solicitud.estado == "cancelada":
            motivo = "solicitud_cancelada"
        else:
            motivo = "ya_asignada"

        raise HTTPException(
            status_code=409,
            detail={
                "type": "urn:m5:problema:solicitud-no-disponible",
                "title": "Solicitud no disponible",
                "status": 409,
                "codigo": "solicitud_no_disponible",
                "motivo": motivo,
            },
        )

    # ── 6. Vigencia de la oferta (410) ──────────────────────────────────────
    if oferta.estado != "pendiente" or _aware(oferta.vence_en) <= ahora:
        raise HTTPException(
            status_code=410,
            detail={
                "type": "urn:m5:problema:oferta-no-vigente",
                "title": "Oferta no vigente",
                "status": 410,
                "codigo": "oferta_no_vigente",
            },
        )

    # ── 7. Procesar respuesta ───────────────────────────────────────────────
    if body.respuesta == "aceptado":
        return _aceptar(db, oferta, solicitud, ahora)
    return _rechazar(db, oferta, solicitud, ahora)


def _aceptar(
    db: Session,
    oferta: Oferta,
    solicitud: Solicitud,
    ahora: datetime,
) -> ResultadoRespuestaOferta:
    """Asigna el conductor de forma atómica. Solo una transacción concurrente puede ganar."""
    r_sol = db.execute(
        update(Solicitud)
        .where(
            Solicitud.solicitud_id == solicitud.solicitud_id,
            Solicitud.estado.in_(list(_ESTADOS_ACTIVOS)),
            Solicitud.conductor_id.is_(None),
        )
        .values(conductor_id=oferta.conductor_id, estado="asignada", fecha_asignacion=ahora)
        .execution_options(synchronize_session=False)
    )
    if r_sol.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "type": "urn:m5:problema:solicitud-no-disponible",
                "title": "Solicitud no disponible",
                "status": 409,
                "codigo": "solicitud_no_disponible",
                "motivo": "ya_asignada",
            },
        )

    r_oferta = db.execute(
        update(Oferta)
        .where(
            Oferta.oferta_id == oferta.oferta_id,
            Oferta.estado == "pendiente",
            Oferta.vence_en > ahora,
        )
        .values(estado="aceptada", respondida_en=ahora)
        .execution_options(synchronize_session=False)
    )
    if r_oferta.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=410,
            detail={
                "type": "urn:m5:problema:oferta-no-vigente",
                "title": "Oferta no vigente",
                "status": 410,
                "codigo": "oferta_no_vigente",
            },
        )

    db.add(HistorialDespacho(
        id_solicitud=solicitud.solicitud_id,
        estado_anterior=solicitud.estado,
        estado_nuevo="asignada",
    ))
    db.commit()

    return ResultadoRespuestaOferta(repetida=False)


def _rechazar(
    db: Session,
    oferta: Oferta,
    solicitud: Solicitud,
    ahora: datetime,
) -> ResultadoRespuestaOferta:
    """Marca la oferta como rechazada. La solicitud sigue en estado activo."""
    r_oferta = db.execute(
        update(Oferta)
        .where(
            Oferta.oferta_id == oferta.oferta_id,
            Oferta.estado == "pendiente",
            Oferta.vence_en > ahora,
        )
        .values(estado="rechazada", respondida_en=ahora)
        .execution_options(synchronize_session=False)
    )
    if r_oferta.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=410,
            detail={
                "type": "urn:m5:problema:oferta-no-vigente",
                "title": "Oferta no vigente",
                "status": 410,
                "codigo": "oferta_no_vigente",
            },
        )

    db.add(HistorialDespacho(
        id_solicitud=solicitud.solicitud_id,
        estado_anterior=solicitud.estado,
        estado_nuevo=solicitud.estado,
    ))
    db.commit()

    return ResultadoRespuestaOferta(repetida=False)

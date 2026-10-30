from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.despacho import HistorialDespacho
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud
from app.schemas.oferta import (
    OfertaCreate,
    OfertaResponse,
    RespuestaOfertaRequest,
    RespuestaOfertaResponse,
)

router = APIRouter(prefix="/ofertas", tags=["Ofertas"])


@router.post("/", response_model=OfertaResponse, status_code=status.HTTP_201_CREATED)
def crear_oferta(oferta_in: OfertaCreate, db: Session = Depends(obtener_db)):
    ahora = datetime.now(timezone.utc)

    # Se usa tiempo_expiracion_seg del schema para calcular la fecha de expiración real
    expiracion = ahora + timedelta(seconds=oferta_in.tiempo_expiracion_seg)

    nueva_oferta = Oferta(
        id_solicitud=oferta_in.id_solicitud,
        conductor_id=oferta_in.conductor_id,
        fecha_envio=ahora,
        fecha_expiracion=expiracion,  # Se asigna a la columna de la base de datos
        estado="PENDIENTE"
    )

    db.add(nueva_oferta)
    db.commit()
    db.refresh(nueva_oferta)

    return nueva_oferta


# RF 5.5 - Aceptar o rechazar ofertas
@router.patch(
    "/{id_oferta}/respuesta",
    response_model=RespuestaOfertaResponse,
    status_code=status.HTTP_200_OK,
    summary="Aceptar o rechazar una oferta de conductor",
)
def responder_oferta(
    id_oferta: str,
    datos: RespuestaOfertaRequest,
    db: Session = Depends(obtener_db),
):
    oferta = db.get(Oferta, id_oferta)
    if not oferta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Oferta no encontrada",
        )

    if oferta.estado != "PENDIENTE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La oferta ya fue respondida. Estado actual: {oferta.estado}",
        )

    solicitud = db.get(Solicitud, oferta.id_solicitud)
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud asociada a la oferta no encontrada",
        )

    if solicitud.cliente_id != datos.cliente_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para responder esta oferta",
        )

    estado_anterior = solicitud.estado

    if datos.accion == "ACEPTAR":
        oferta.estado = "ACEPTADA"
        solicitud.estado = "ACEPTADA"
        mensaje = "Oferta aceptada. El conductor fue asignado a la solicitud."
    else:
        oferta.estado = "RECHAZADA"
        solicitud.estado = "PENDIENTE"
        mensaje = "Oferta rechazada. La solicitud queda pendiente de nueva asignación."

    db.add(HistorialDespacho(
        id_solicitud=solicitud.solicitud_id,
        estado_anterior=estado_anterior,
        estado_nuevo=solicitud.estado,
    ))

    db.commit()
    db.refresh(oferta)
    db.refresh(solicitud)

    return RespuestaOfertaResponse(
        id_oferta=oferta.id_oferta,
        id_solicitud=oferta.id_solicitud,
        estado_oferta=oferta.estado,
        estado_solicitud=solicitud.estado,
        mensaje=mensaje,
    )

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.oferta import Oferta
from app.models.solicitud import Solicitud
from app.schemas.oferta import (
    EstadoOferta,
    OfertaCreate,
    OfertaResponse,
    RespuestaOfertaRequest,
    ResultadoRespuestaOferta,
)
from app.services.asignacion import procesar_respuesta_oferta
from app.services.ofertas_service import procesar_ofertas_vencidas

router = APIRouter(tags=["Ofertas"])


@router.get(
    "/solicitudes/{solicitud_id}/ofertas",
    response_model=List[OfertaResponse],
    summary="Consultar ofertas de una solicitud",
)
def listar_ofertas_solicitud(
    solicitud_id: UUID,
    db: Session = Depends(obtener_db),
):
    solicitud = (
        db.query(Solicitud)
        .filter(Solicitud.solicitud_id == str(solicitud_id))
        .first()
    )
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada",
        )

    procesar_ofertas_vencidas(db)

    return (
        db.query(Oferta)
        .filter(Oferta.solicitud_id == str(solicitud_id))
        .order_by(Oferta.creada_en.asc())
        .all()
    )


@router.get(
    "/conductores/{conductor_id}/ofertas",
    response_model=List[OfertaResponse],
    summary="Consultar ofertas de un conductor",
)
def listar_ofertas_conductor(
    conductor_id: UUID,
    estado: Optional[EstadoOferta] = Query(
        default=None, description="Filtra por el estado de la oferta."
    ),
    db: Session = Depends(obtener_db),
):
    procesar_ofertas_vencidas(db)

    query = db.query(Oferta).filter(Oferta.conductor_id == str(conductor_id))
    if estado is not None:
        query = query.filter(Oferta.estado == estado.value)

    return query.order_by(Oferta.creada_en.desc()).all()


@router.post(
    "/ofertas/",
    response_model=OfertaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear oferta para un conductor",
)
def crear_oferta(oferta_in: OfertaCreate, db: Session = Depends(obtener_db)):
    ahora = datetime.now(timezone.utc)
    nueva_oferta = Oferta(
        solicitud_id=oferta_in.solicitud_id,
        conductor_id=oferta_in.conductor_id,
        vence_en=ahora + timedelta(seconds=oferta_in.tiempo_expiracion_seg),
    )
    db.add(nueva_oferta)
    db.commit()
    db.refresh(nueva_oferta)
    return nueva_oferta


@router.post(
    "/ofertas/{oferta_id}/responder",
    response_model=ResultadoRespuestaOferta,
    status_code=status.HTTP_200_OK,
    summary="Registrar respuesta de conductor recibida de M3 (RF-5.5)",
    description=(
        "M3 envía la decisión del conductor: aceptado o rechazado. "
        "Una aceptación asigna el conductor a la solicitud de forma atómica. "
        "Un rechazo registra la decisión y la solicitud sigue en búsqueda. "
        "Una respuesta idéntica ya registrada devuelve repetida=true."
    ),
)
def responder_oferta(
    oferta_id: str,
    body: RespuestaOfertaRequest,
    db: Session = Depends(obtener_db),
):
    if oferta_id != body.oferta_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "urn:m5:problema:datos-invalidos",
                "title": "Datos inválidos",
                "status": 400,
                "detail": "El oferta_id del cuerpo no coincide con el de la URL",
            },
        )
    return procesar_respuesta_oferta(db, oferta_id, body)

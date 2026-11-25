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
    RespuestaOfertaResponse,
)
from app.services.asignacion import asignar_conductor, rechazar_oferta
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

@router.post("/ofertas/", response_model=OfertaResponse, status_code=status.HTTP_201_CREATED)
def crear_oferta(oferta_in: OfertaCreate, db: Session = Depends(obtener_db)):
    ahora = datetime.now(timezone.utc)
    expiracion = ahora + timedelta(seconds=oferta_in.tiempo_expiracion_seg)

    nueva_oferta = Oferta(
        id_solicitud=oferta_in.id_solicitud,
        conductor_id=oferta_in.conductor_id,
        fecha_envio=ahora,
        fecha_expiracion=expiracion,
        estado="PENDIENTE",
    )
    db.add(nueva_oferta)
    db.commit()
    db.refresh(nueva_oferta)
    return nueva_oferta


@router.patch(
    "/ofertas/{id_oferta}/respuesta",
    response_model=RespuestaOfertaResponse,
    status_code=status.HTTP_200_OK,
    summary="Aceptar o rechazar una oferta (RF-5.5)",
    description=(
        "El conductor responde una oferta mientras esté vigente. "
        "ACEPTAR asigna el conductor a la solicitud (con protección de concurrencia). "
        "RECHAZAR libera la oferta y deja la solicitud en PENDIENTE."
    ),
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

    solicitud = db.get(Solicitud, oferta.id_solicitud)
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud asociada no encontrada",
        )

    if solicitud.cliente_id != datos.cliente_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para responder esta oferta",
        )

    if datos.accion == "ACEPTAR":
        return asignar_conductor(db, id_oferta)
    return rechazar_oferta(db, id_oferta)

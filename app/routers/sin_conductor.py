from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.services.sin_conductor import marcar_sin_conductor, vencer_busquedas

router = APIRouter(tags=["Sin conductor (RF-5.8)"])


class SinConductorRequest(BaseModel):
    motivo: Literal["SIN_CANDIDATOS", "BUSQUEDA_VENCIDA"] = "SIN_CANDIDATOS"


class SinConductorResponse(BaseModel):
    solicitud_id: UUID
    estado: str
    motivo: str
    mensaje: str
    ya_registrada: bool


class VencerBusquedasResponse(BaseModel):
    timeout_seg: int
    cantidad: int
    solicitudes: list[UUID]


@router.post(
    "/solicitudes/{solicitud_id}/sin-conductor",
    response_model=SinConductorResponse,
    status_code=status.HTTP_200_OK,
    summary="Informar que no hay conductores disponibles (RF-5.8)",
)
def informar_sin_conductor(
    solicitud_id: UUID,
    datos: SinConductorRequest | None = None,
    db: Session = Depends(obtener_db),
):
    motivo = datos.motivo if datos else "SIN_CANDIDATOS"
    return marcar_sin_conductor(db, str(solicitud_id), motivo)


@router.post(
    "/solicitudes/vencer-busquedas",
    response_model=VencerBusquedasResponse,
    status_code=status.HTTP_200_OK,
    summary="Vencer las búsquedas que superaron el plazo (RF-5.8)",
)
def vencer_busquedas_expiradas(db: Session = Depends(obtener_db)):
    return vencer_busquedas(db)

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.despacho import HistorialDespacho
from app.models.solicitud import Solicitud
from app.schemas.busqueda import RespuestaBusqueda
from app.services import clientes_m4
from app.services.clientes_m4 import ErrorIntegracionM4

# Estados según el contrato del Grupo 4 (snake_case minúscula)
ESTADO_PENDIENTE = "pendiente"
ESTADO_BUSCANDO = "buscando"
ESTADO_SIN_DISPONIBILIDAD = "sin_disponibilidad"
EVENTO_ERROR_INTEGRACION = "ERROR_INTEGRACION"


def _registrar(db: Session, solicitud_id: str, anterior: str, nuevo: str) -> None:
    db.add(HistorialDespacho(
        id_solicitud=solicitud_id,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        fecha_cambio=datetime.now(timezone.utc),
    ))


def iniciar_busqueda(db: Session, solicitud_id: str) -> RespuestaBusqueda:
    """RF-5.3: busca conductores candidatos para una solicitud.

    Pasa la solicitud a 'buscando', consulta a M4 (solo lectura, no reserva a nadie)
    y devuelve los candidatos compatibles ordenados del más cercano al más lejano.
    Si M4 no tiene conductores, la solicitud queda 'sin_disponibilidad'.
    Si M4 falla, la solicitud sigue 'buscando': un error nunca equivale a lista vacía.
    """
    solicitud = db.get(Solicitud, solicitud_id)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="La solicitud no fue encontrada.")

    # Se copian los datos antes de los commits, que "vencen" el objeto.
    estado_inicial = solicitud.estado
    origen_latitud = solicitud.origen_latitud
    origen_longitud = solicitud.origen_longitud
    tipo_vehiculo = solicitud.tipo_vehiculo

    # 1) Pasar a 'buscando' una sola vez (acepta 'PENDIENTE' o 'pendiente')
    resultado = db.execute(
        update(Solicitud)
        .where(
            Solicitud.solicitud_id == solicitud_id,
            func.lower(Solicitud.estado) == ESTADO_PENDIENTE,
        )
        .values(estado=ESTADO_BUSCANDO)
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"No se puede iniciar la búsqueda: el estado actual es '{estado_inicial}'.",
        )
    _registrar(db, solicitud_id, estado_inicial, ESTADO_BUSCANDO)
    db.commit()

    # 2) Consultar a M4 (fuera de cualquier transacción)
    try:
        resultado_m4 = clientes_m4.buscar_candidatos(
            origen_latitud, origen_longitud, tipo_vehiculo
        )
    except ErrorIntegracionM4 as error:
        _registrar(db, solicitud_id, ESTADO_BUSCANDO, EVENTO_ERROR_INTEGRACION)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo consultar a M4. La solicitud sigue en búsqueda. ({error})",
        )

    # 3) Quedarse con candidatos compatibles, sin repetidos, del más cercano al más lejano
    candidatos = []
    vistos = set()
    for candidato in sorted(resultado_m4.conductores, key=lambda c: c.distancia_origen_km):
        if candidato.tipo_vehiculo != tipo_vehiculo or candidato.conductor_id in vistos:
            continue
        vistos.add(candidato.conductor_id)
        candidatos.append(candidato)

    # 4) Sin candidatos: la búsqueda se agotó
    estado_final = ESTADO_BUSCANDO
    mensaje = "Búsqueda realizada: candidatos encontrados"
    if not candidatos:
        agotada = db.execute(
            update(Solicitud)
            .where(
                Solicitud.solicitud_id == solicitud_id,
                Solicitud.estado == ESTADO_BUSCANDO,
            )
            .values(estado=ESTADO_SIN_DISPONIBILIDAD)
            .execution_options(synchronize_session=False)
        )
        if agotada.rowcount == 1:
            _registrar(db, solicitud_id, ESTADO_BUSCANDO, ESTADO_SIN_DISPONIBILIDAD)
            db.commit()
            estado_final = ESTADO_SIN_DISPONIBILIDAD
            mensaje = "Búsqueda agotada: no hay conductores disponibles"
        else:
            # Cambió mientras tanto (por ejemplo, el cliente canceló): se informa el estado real
            db.rollback()
            estado_final = db.scalar(
                select(Solicitud.estado).where(Solicitud.solicitud_id == solicitud_id)
            )
            mensaje = "La solicitud cambió de estado durante la búsqueda"

    return RespuestaBusqueda(
        mensaje=mensaje,
        solicitud_id=solicitud_id,
        estado=estado_final,
        radio_aplicado_km=resultado_m4.radio_aplicado_km,
        generado_en=resultado_m4.generado_en,
        candidatos=candidatos,
    )
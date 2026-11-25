from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from opentelemetry import metrics

from app.models.oferta import Oferta
from app.models.solicitud import Solicitud
from app.schemas.oferta import ItemOfertaM3, LoteOfertasM3

PLAZO_OFERTA_SEGUNDOS = 30

meter = metrics.get_meter("m5.despacho")
ofertas_finalizadas_counter = meter.create_counter(
    name="m5.ofertas.finalizadas",
    description="Cantidad de ofertas finalizadas por desenlace",
)


def emitir_lote_ofertas(
    db: Session, solicitud: Solicitud, conductores_ids: List[str]
) -> LoteOfertasM3:
    """Crea las ofertas en BD con vencimiento compartido de 30s UTC y arma el lote para M3."""
    ahora = datetime.now(timezone.utc)
    vence_en = ahora + timedelta(seconds=PLAZO_OFERTA_SEGUNDOS)

    ofertas_creadas: List[Oferta] = []
    for conductor_id in conductores_ids:
        oferta = Oferta(
            solicitud_id=str(solicitud.solicitud_id),
            conductor_id=str(conductor_id),
            estado="pendiente",
            creada_en=ahora,
            vence_en=vence_en,
        )
        db.add(oferta)
        ofertas_creadas.append(oferta)

    db.commit()
    for oferta in ofertas_creadas:
        db.refresh(oferta)

    return LoteOfertasM3(
        solicitud_id=solicitud.solicitud_id,
        origen_latitud=solicitud.origen_latitud,
        origen_longitud=solicitud.origen_longitud,
        destino_latitud=solicitud.destino_latitud,
        destino_longitud=solicitud.destino_longitud,
        tipo_vehiculo=solicitud.tipo_vehiculo,
        ofertas=[
            ItemOfertaM3(oferta_id=o.oferta_id, conductor_id=o.conductor_id)
            for o in ofertas_creadas
        ],
        vence_en=vence_en,
    )


def procesar_ofertas_vencidas(db: Session) -> int:
    """Marca como 'vencida' toda oferta pendiente cuyo vence_en haya expirado."""
    ahora = datetime.now(timezone.utc)
    vencidas = (
        db.query(Oferta)
        .filter(Oferta.estado == "pendiente", Oferta.vence_en <= ahora)
        .all()
    )

    if not vencidas:
        return 0

    for oferta in vencidas:
        oferta.estado = "vencida"

    db.commit()

    # Métrica 3 de DevOps: registrar desenlace vencida tras el commit
    ofertas_finalizadas_counter.add(
        len(vencidas), {"resultado": "vencida", "m5.impl": "G13"}
    )
    return len(vencidas)
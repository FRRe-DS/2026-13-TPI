from opentelemetry import metrics

_meter = metrics.get_meter("m5.despacho")

# Métrica 1: Tiempo total desde creación de solicitud hasta asignación (Histograma)
tiempo_asignacion_hist = _meter.create_histogram(
    name="m5.solicitud.tiempo_asignacion",
    unit="s",
    description="Tiempo transcurrido desde la creacion de la solicitud hasta la asignacion",
)

# Métrica 2: Desenlace final de solicitudes (Contador)
solicitudes_cerradas_counter = _meter.create_counter(
    name="m5.solicitudes.cerradas",
    description="Cantidad de solicitudes finalizadas por estado terminal",
)

# Métrica 3: Desenlace final de ofertas (Contador)
ofertas_finalizadas_counter = _meter.create_counter(
    name="m5.ofertas.finalizadas",
    description="Cantidad de ofertas finalizadas por desenlace",
)


def registrar_tiempo_asignacion(segundos: float) -> None:
    """Registra en segundos cuánto demoró asignarse una solicitud (RF-5.1 -> RF-5.6)."""
    if segundos >= 0:
        tiempo_asignacion_hist.record(segundos, {"m5.impl": "G13"})


def registrar_solicitud_cerrada(estado: str) -> None:
    """
    Registra el cierre de una solicitud.
    Valores válidos para `estado`: 'asignada', 'sin_disponibilidad', 'cancelada'.
    """
    solicitudes_cerradas_counter.add(1, {"estado": estado, "m5.impl": "G13"})


def registrar_oferta_finalizada(resultado: str, cantidad: int = 1) -> None:
    """
    Registra el desenlace de una o más ofertas.
    Valores válidos para `resultado`: 'aceptada', 'rechazada', 'vencida', 'cancelada'.
    """
    if cantidad > 0:
        ofertas_finalizadas_counter.add(
            cantidad, {"resultado": resultado, "m5.impl": "G13"}
        )
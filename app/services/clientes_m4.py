import os
import time
from uuid import UUID, uuid4

import httpx

from app.schemas.busqueda import (
    ResultadoBusquedaM4,
    ResultadoReservaM4,
)

RUTA_CERCANOS = "/api/v1/conductores/cercanos"
RUTA_RESERVA = "/api/v1/conductores/{conductor_id}/reserva"
ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}


class ErrorIntegracionM4(Exception):
    """M4 no pudo responder bien. Esto NUNCA equivale a 'lista vacía'."""


class ConflictoReservaM4(Exception):
    """M4 respondió 409.

    Al reservar: otra solicitud ya tiene a ese conductor (o no es elegible);
    hay que pasar al siguiente candidato.
    Al liberar: la solicitud_id no coincide con la de la reserva.
    """


def buscar_candidatos(
    origen_latitud: float,
    origen_longitud: float,
    tipo_vehiculo: str,
    limite: int = 20,
    intentos: int = 3,
    espera_seg: float = 0.5,
    cliente: httpx.Client | None = None,
) -> ResultadoBusquedaM4:
    """Consulta a M4 los conductores cercanos al origen (RF-5.3).

    Es de solo lectura: no reserva a nadie. M4 amplía el radio por su cuenta
    (5, 6.5, 8 y 9.5 km) y devuelve la lista ordenada del más cercano al más lejano.
    """
    base_url = os.getenv("M4_BASE_URL", "http://localhost:8004")
    timeout = float(os.getenv("M4_TIMEOUT_SEG", "3"))
    token = os.getenv("M4_TOKEN")

    cabeceras = {"X-Request-Id": str(uuid4())}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"

    parametros = {
        "origen_latitud": origen_latitud,
        "origen_longitud": origen_longitud,
        "tipo_vehiculo": tipo_vehiculo,
        "limite": limite,
    }

    cliente_propio = cliente is None
    if cliente_propio:
        cliente = httpx.Client(base_url=base_url, timeout=timeout)

    try:
        ultimo_error = "sin intentos"
        for intento in range(1, intentos + 1):
            try:
                respuesta = cliente.get(RUTA_CERCANOS, params=parametros, headers=cabeceras)
            except httpx.TimeoutException:
                ultimo_error = "M4 no respondió a tiempo (timeout)"
            except httpx.TransportError:
                ultimo_error = "No se pudo conectar con M4"
            else:
                if respuesta.status_code == 200:
                    try:
                        return ResultadoBusquedaM4.model_validate(respuesta.json())
                    except ValueError:
                        raise ErrorIntegracionM4("M4 devolvió una respuesta con formato inválido")
                if respuesta.status_code not in ESTADOS_REINTENTABLES:
                    raise ErrorIntegracionM4(
                        f"M4 rechazó la búsqueda (HTTP {respuesta.status_code})"
                    )
                ultimo_error = f"M4 respondió HTTP {respuesta.status_code}"

            if intento < intentos:
                time.sleep(espera_seg)

        raise ErrorIntegracionM4(f"{ultimo_error} tras {intentos} intentos")
    finally:
        if cliente_propio:
            cliente.close()


def _cambiar_reserva(
    conductor_id: str | UUID,
    solicitud_id: str | UUID,
    estado_temporal: str,
    clave_idempotencia: str,
    intentos: int,
    espera_seg: float,
    cliente: httpx.Client | None,
) -> ResultadoReservaM4:
    """Envía a M4 el pedido RESERVADO o LIBERADO para un conductor y una solicitud."""
    base_url = os.getenv("M4_BASE_URL", "http://localhost:8004")
    timeout = float(os.getenv("M4_TIMEOUT_SEG", "3"))
    token = os.getenv("M4_TOKEN")

    # La misma clave en todos los reintentos: M4 no repite el efecto.
    cabeceras = {
        "X-Request-Id": str(uuid4()),
        "Idempotency-Key": clave_idempotencia,
    }
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"

    ruta = RUTA_RESERVA.format(conductor_id=conductor_id)
    # Solo conductor_id (en la ruta) y solicitud_id: sin motivo ni oferta_id.
    cuerpo = {"estado_temporal": estado_temporal, "solicitud_id": str(solicitud_id)}

    cliente_propio = cliente is None
    if cliente_propio:
        cliente = httpx.Client(base_url=base_url, timeout=timeout)

    try:
        ultimo_error = "sin intentos"
        for intento in range(1, intentos + 1):
            try:
                respuesta = cliente.post(ruta, json=cuerpo, headers=cabeceras)
            except httpx.TimeoutException:
                ultimo_error = "M4 no respondió a tiempo (timeout)"
            except httpx.TransportError:
                ultimo_error = "No se pudo conectar con M4"
            else:
                if respuesta.status_code in (200, 201):
                    try:
                        return ResultadoReservaM4.model_validate(respuesta.json())
                    except ValueError:
                        raise ErrorIntegracionM4("M4 devolvió una respuesta con formato inválido")
                if respuesta.status_code == 409:
                    raise ConflictoReservaM4(
                        f"M4 informó un conflicto al pasar el conductor a {estado_temporal}"
                    )
                if respuesta.status_code not in ESTADOS_REINTENTABLES:
                    raise ErrorIntegracionM4(
                        f"M4 rechazó el cambio de reserva (HTTP {respuesta.status_code})"
                    )
                ultimo_error = f"M4 respondió HTTP {respuesta.status_code}"

            if intento < intentos:
                time.sleep(espera_seg)

        raise ErrorIntegracionM4(f"{ultimo_error} tras {intentos} intentos")
    finally:
        if cliente_propio:
            cliente.close()


def reservar_conductor(
    conductor_id: str | UUID,
    solicitud_id: str | UUID,
    idempotency_key: str | None = None,
    intentos: int = 3,
    espera_seg: float = 0.5,
    cliente: httpx.Client | None = None,
) -> ResultadoReservaM4:
    """Reserva temporalmente a UN conductor para una solicitud (M4 lo bloquea 10 minutos).

    Si otra solicitud ya lo reservó, lanza ConflictoReservaM4: hay que pasar al siguiente.
    """
    clave = idempotency_key or f"reserva-{solicitud_id}-{conductor_id}"
    return _cambiar_reserva(
        conductor_id, solicitud_id, "RESERVADO", clave, intentos, espera_seg, cliente
    )


def liberar_conductor(
    conductor_id: str | UUID,
    solicitud_id: str | UUID,
    idempotency_key: str | None = None,
    intentos: int = 3,
    espera_seg: float = 0.5,
    cliente: httpx.Client | None = None,
) -> ResultadoReservaM4:
    """Libera la reserva de un conductor. El mensaje es el mismo sin importar el motivo.

    Repetir la liberación no tiene efectos adicionales. Usa una clave distinta
    a la de reservar, como pide M4.
    """
    clave = idempotency_key or f"liberacion-{solicitud_id}-{conductor_id}"
    return _cambiar_reserva(
        conductor_id, solicitud_id, "LIBERADO", clave, intentos, espera_seg, cliente
    )
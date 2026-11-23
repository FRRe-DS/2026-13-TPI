import os
import time
from uuid import uuid4

import httpx

from app.schemas.busqueda import ResultadoBusquedaM4

RUTA_CERCANOS = "/api/v1/conductores/cercanos"
ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}


class ErrorIntegracionM4(Exception):
    """M4 no pudo responder bien. Esto NUNCA equivale a 'lista vacía'."""


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
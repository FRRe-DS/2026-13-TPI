# Integraciones del módulo M5

## 1. Objetivo

Documentar los intercambios de información necesarios entre M5 — Solicitud y Despacho y los demás módulos de la plataforma.

Los acuerdos de datos registrados en este documento servirán como base para definir los contratos OpenAPI entre equipos.

**Estado actual:** las integraciones todavía no están implementadas.

## 2. M2 — Clientes

**Estado:** intercambio de datos acordado.

M5 necesita consultar la habilitación de un cliente antes de utilizar sus datos en el proceso de solicitud y despacho.

**Datos enviados por M5:**
- `cliente_id`: UUID.

**Datos recibidos desde M2:**
- `cliente_id`: UUID.
- `habilitado`: booleano.

M2 es propietario de los datos del cliente.

## 3. M3 — Conductores y Vehículos

**Estado:** intercambio de datos acordado.

M5 necesita verificar que un conductor esté habilitado y conocer el vehículo que utiliza actualmente.

**Datos enviados por M5:**
- `conductor_id`: UUID.

**Datos recibidos desde M3:**
- `conductor_id`: UUID.
- `habilitado`: booleano.
- `disponible`: booleano.
- `vehiculo`:
  - `vehiculo_id`: UUID.
  - `tipo_vehiculo`: `AUTO` o `MOTO`.

El atributo `vehiculo` representa el vehículo activo del conductor, aunque tenga otros vehículos registrados.

## 4. M4 — Ubicación y Disponibilidad

**Estado:** intercambio de datos acordado; rutas y operaciones HTTP pendientes de formalización.

M5 necesita solicitar candidatos cercanos al origen de un viaje.

**Datos enviados por M5:**
- `solicitud_id`: UUID.
- `origen_latitud`: número.
- `origen_longitud`: número.
- `destino_latitud`: número.
- `destino_longitud`: número.
- `tipo_vehiculo`: `AUTO` o `MOTO`.
- `radio_maximo_km`: número.

**Datos recibidos desde M4:**
- `solicitud_id`: UUID.
- `conductores`: lista de candidatos con:
  - `conductor_id`: UUID.
  - `distancia_km`: número.
  - `eta_minutos`: entero.

M4 es responsable de aplicar los filtros de ubicación y disponibilidad temporal.

La operación de bloqueo de un conductor deberá formalizarse mediante un contrato específico.

## 5. M6 — Viajes y Ciclo de Vida

**Estado:** intercambio de datos confirmado con el equipo M6.

Después de asignar un conductor, M5 necesitará comunicar a M6 los datos necesarios para crear el viaje.

**Datos propuestos para enviar:**
- `solicitud_id`: UUID.
- `cliente_id`: UUID.
- `conductor_id`: UUID.
- `vehiculo_id`: UUID.
- Coordenadas de origen y destino.

**Datos propuestos para recibir:**
- `viaje_id`: UUID.
- `solicitud_id`: UUID.
- `estado`: estado inicial del viaje.

Los campos definitivos, las rutas y las respuestas de error deberán acordarse con el equipo de M6.

## 6. M9 — Reservas de Viajes

**Estado:** intercambio de datos confirmado con el equipo M9.

M9 deberá poder solicitar la activación de una reserva para generar una solicitud de despacho.

**Datos propuestos para recibir desde M9:**
- `reserva_id`: UUID.
- `cliente_id`: UUID.
- Coordenadas de origen y destino.
- `tipo_vehiculo`: `AUTO` o `MOTO`.

**Datos propuestos para devolver a M9:**
- `reserva_id`: UUID.
- `solicitud_id`: UUID.
- `estado`: estado de la solicitud.

La activación deberá diseñarse para evitar que una misma reserva genere solicitudes duplicadas.

### Casos especiales acordados con M9

**1. Error al registrar una solicitud**

Si M5 no puede registrar una solicitud proveniente de una reserva, deberá devolver una respuesta de error. M9 realizará como máximo un reintento.

M5 deberá evitar que los reintentos generen solicitudes duplicadas para una misma reserva.

**2. Reserva sin conductor disponible**

Si una solicitud originada por una reserva no consigue conductor dentro del tiempo de espera establecido, M5 deberá informar el resultado a M9.

M9 será responsable de actualizar el estado de la reserva a `VENCIDA` y coordinar la notificación correspondiente con M8.

**3. Responsabilidades**

- **M5:** creación de solicitudes, búsqueda de conductores e información del resultado del despacho.
- **M9:** gestión del estado de las reservas, incluidos sus vencimientos.
- **M8:** envío de las notificaciones correspondientes.

**Pendiente de formalización:** definir el mecanismo mediante el cual M5 informa a M9 que no se consiguió conductor, los códigos de error y el tiempo máximo de espera.

## 7. Formalización de contratos

Los intercambios de datos acordados deberán completarse con:

- Métodos y rutas HTTP.
- Esquemas de solicitud y respuesta en OpenAPI.
- Códigos de estado y respuestas de error.
- Responsabilidades ante fallas de comunicación.
- Eventos publicados o consumidos, cuando corresponda.

Los contratos deberán validarse con los equipos involucrados antes de considerarse definitivos.

## 8. Estado de implementación

Actualmente M5 registra solicitudes de viaje mediante su API REST y las almacena en MySQL.

Las consultas y operaciones entre módulos quedan pendientes de implementación según el alcance de las próximas etapas del TPI.
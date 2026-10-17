# Desarrollo de Software 2026 — TPI

## Grupo 13 — M5: Solicitud y Despacho

### Descripción del proyecto

Este repositorio corresponde al **Trabajo Práctico Integrador (TPI)** de la asignatura Desarrollo de Software — 2026.

El proyecto consiste en desarrollar una **plataforma distribuida de movilidad urbana bajo demanda**, que permita conectar clientes que solicitan viajes con conductores habilitados para prestar servicios de transporte en auto o moto.

Nuestro grupo tiene asignado el **Módulo M5 — Solicitud y Despacho**, responsable de gestionar solicitudes de viaje, buscar conductores disponibles, enviar ofertas y garantizar la asignación de un único conductor por solicitud.

### Integrantes — Grupo 13

1. Barberan, Facundo
2. Bassi, Ayelen
3. Escalante, Alejo
4. Franco, Ivan
5. Lopez, Agustin
6. Mendez, Joaquin
7. Quiroz, Ariel
8. Samardich, Agustin
9. Servin, Santiago

### Tecnologías utilizadas

| Tecnología | Propósito |
|---|---|
| Python 3.10 | Lenguaje de programación |
| FastAPI | Desarrollo de la API REST |
| SQLAlchemy | Acceso y persistencia de datos mediante ORM |
| MySQL 8.4 | Base de datos relacional |
| PyMySQL | Conexión entre Python y MySQL |
| Docker y Docker Compose | Ejecución de la API y la base de datos en contenedores |
| OpenAPI / Swagger | Documentación y pruebas de endpoints |
| pytest y HTTPX | Pruebas automatizadas |
| Git y GitHub | Control de versiones y trabajo colaborativo |

### Requerimientos funcionales — M5

| ID | Requerimiento |
|---|---|
| RF-5.1 | Solicitud de viaje inmediato |
| RF-5.2 | Solicitud desde reserva |
| RF-5.3 | Búsqueda de candidatos |
| RF-5.4 | Oferta con vencimiento |
| RF-5.5 | Aceptar o rechazar ofertas |
| RF-5.6 | Asignación única |
| RF-5.7 | Cancelación previa |
| RF-5.8 | Sin disponibilidad |
| RF-5.9 | Trazabilidad del despacho |

Estos requerimientos corresponden al alcance funcional general del módulo M5. Su implementación se realizará progresivamente según las entregas establecidas en el Readme 2026-TPI.

### Integración con otros módulos

El módulo M5 deberá comunicarse con los siguientes servicios:

- **M2 — Clientes:** consulta de identificación y habilitación del cliente.
- **M3 — Conductores y Vehículos:** consulta de habilitación, disponibilidad general y vehículo activo del conductor.
- **M4 — Ubicación y Disponibilidad:** búsqueda de conductores cercanos y gestión de bloqueos temporales.
- **M6 — Viajes y Ciclo de Vida:** creación del viaje después de confirmar la asignación.
- **M9 — Reservas de Viajes:** activación de solicitudes provenientes de reservas, evitando solicitudes duplicadas.

Los intercambios de datos con M2, M3 y M4 fueron acordados entre los equipos. Las propuestas para M6 y M9 están pendientes de confirmación.

La implementación de la comunicación real entre módulos queda pendiente para próximas etapas, según el alcance definido por la cátedra.

### Estructura del proyecto

```text
app/
  models/
    solicitud.py
  database.py
  main.py
Contratos/
  openapi.yml
tests/
  conftest.py
  test_main.py
Dockerfile
compose.yaml
crear_tablas.py
requirements.txt
.env.example
README.md
```

### Ejecución del proyecto

Para ejecutar el proyecto es necesario tener instalados **Docker y Docker Compose**.

1. Clonar el repositorio y acceder a su carpeta.
2. Crear un archivo `.env` a partir de `.env.example`, completando las contraseñas de MySQL.
3. Construir e iniciar los servicios:

```bash
docker compose up -d --build
```

4. Crear las tablas de la base de datos, si todavía no existen:

```bash
docker compose exec api python crear_tablas.py
```

5. Acceder a la documentación interactiva de la API:

`http://localhost:8000/docs`

La API utiliza el puerto `8000` y MySQL se encuentra disponible desde la computadora mediante el puerto `3307`.

### Endpoints implementados

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Devuelve un mensaje de bienvenida del módulo M5 |
| POST | `/solicitudes` | Registra una solicitud de viaje con identificador del cliente, coordenadas de origen y destino y tipo de vehículo |

El endpoint `POST /solicitudes` recibe los siguientes atributos:

- `cliente_id`: identificador UUID del cliente.
- `origen_latitud` y `origen_longitud`: coordenadas del punto de origen.
- `destino_latitud` y `destino_longitud`: coordenadas del destino.
- `tipo_vehiculo`: `AUTO` o `MOTO`.

Cuando la solicitud se registra correctamente, la API devuelve el código HTTP `201`, un `solicitud_id` generado automáticamente y el estado inicial `PENDIENTE`.

Actualmente, la creación de solicitudes constituye una implementación inicial del requerimiento **RF-5.1**. Todavía no representa el flujo completo de solicitud y despacho.

### Persistencia de datos

El módulo utiliza **MySQL** para almacenar las solicitudes de viaje mediante SQLAlchemy.

Cada solicitud registrada contiene:

- `solicitud_id`: identificador UUID generado automáticamente.
- `cliente_id`: identificador del cliente.
- Coordenadas de origen y destino.
- `tipo_vehiculo`: tipo de vehículo solicitado.
- `estado`: inicialmente `PENDIENTE`.
- `fecha_creacion`: fecha y hora de registro.

La base de datos utiliza un volumen de Docker para conservar la información almacenada.

### Pruebas automatizadas

El proyecto utiliza **pytest** para ejecutar pruebas automatizadas.

Actualmente se incluyen:

- Una prueba del endpoint `GET /`.
- Una prueba de integración del endpoint `POST /solicitudes`, utilizando una base de datos independiente llamada `m5_test_db`.

Para ejecutar las pruebas desde el entorno virtual de Python:

```bash
python -m pytest -v
```

Las pruebas de integración requieren que MySQL esté en funcionamiento y que la base de datos de pruebas esté creada y tenga los permisos correspondientes.

### Contrato OpenAPI

El contrato OpenAPI de los endpoints implementados se encuentra en:

`Contratos/openapi.yml`

Este archivo documenta la estructura de las solicitudes, las respuestas y los errores de validación.

La especificación se mantiene consistente con la implementación de FastAPI y fue verificada mediante Swagger Editor.

La publicación del contrato correspondiente en el repositorio general de la cátedra queda pendiente de coordinación.

### Estado del proyecto

**En desarrollo — Primera entrega (TP1).**

Hasta el momento se implementaron:

- Estructura inicial de la API con FastAPI.
- Endpoint para registrar solicitudes de viaje con UUID y coordenadas.
- Validación de los tipos de vehículo `AUTO` y `MOTO`.
- Persistencia de solicitudes en MySQL mediante SQLAlchemy.
- Ejecución de FastAPI y MySQL mediante Docker Compose.
- Pruebas automatizadas del endpoint de inicio y de creación de solicitudes.
- Contrato OpenAPI del endpoint implementado.

Continúan pendientes las funcionalidades de despacho, búsqueda de conductores, gestión de ofertas, asignación única y comunicación real con los demás módulos.

---

**Asignatura:** Desarrollo de Software  
**Año:** 2026  
**Grupo:** 13  
**Módulo asignado:** M5 — Solicitud y Despacho
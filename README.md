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

Estos requerimientos corresponden al alcance funcional general del módulo M5. Su implementación se realizará progresivamente según las entregas establecidas por la cátedra.

### Integración con otros módulos

El módulo M5 deberá comunicarse con los siguientes servicios:

- **M2 — Clientes:** información del cliente.
- **M3 — Conductores y Vehículos:** habilitación de conductores y vehículos.
- **M4 — Ubicación y Disponibilidad:** búsqueda de conductores cercanos y disponibles.
- **M6 — Viajes y Ciclo de Vida:** coordinación de la asignación y el inicio del ciclo del viaje.
- **M9 — Reservas de Viajes:** activación de solicitudes provenientes de reservas.

La integración entre módulos se realizará mediante APIs y eventos, respetando la independencia y propiedad de los datos de cada servicio.

### Estructura del proyecto

```text
app/
  models/
    solicitud.py
  database.py
  main.py
tests/
  conftest.py
  test_main.py
Dockerfile
compose.yaml
crear_tablas.py
requirements.txt
.env.example
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
docker docker compose exec api python crear_tablas.py
```

5. Acceder a la documentación interactiva de la API:

`http://localhost:8000/docs`

La API utiliza el puerto `8000` y MySQL se encuentra disponible desde la computadora mediante el puerto `3307`.

### Endpoints implementados

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Devuelve un mensaje de bienvenida del módulo M5 |
| POST | `/solicitudes` | Registra una solicitud de viaje con origen, destino y tipo de vehículo |

Actualmente, la creación de solicitudes constituye una implementación inicial del requerimiento **RF-5.1**. Todavía no representa el flujo completo de solicitud y despacho.

### Persistencia de datos

El módulo utiliza **MySQL** para almacenar las solicitudes de viaje mediante SQLAlchemy.

Cada solicitud registrada contiene un identificador, origen, destino, tipo de vehículo, estado y fecha de creación.

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

El contrato de comunicación del módulo M5 se documentará en el archivo `contratos/m5_solicitud/openapi.yml` del repositorio general de la cátedra.

Este contrato deberá mantenerse consistente con los endpoints implementados por nuestro servicio.

### Estado del proyecto

**En desarrollo — Primera entrega (TP1).**

Hasta el momento se implementaron:

- Estructura inicial de la API con FastAPI.
- Endpoint básico para registrar solicitudes de viaje.
- Persistencia de solicitudes en MySQL mediante SQLAlchemy.
- Ejecución de FastAPI y MySQL mediante Docker Compose.
- Pruebas automatizadas del endpoint de inicio y de creación de solicitudes.

Continúan pendientes las funcionalidades de despacho, búsqueda de conductores, gestión de ofertas, asignación única y demás requerimientos.

---

**Asignatura:** Desarrollo de Software  
**Año:** 2026  
**Grupo:** 13  
**Módulo asignado:** M5 — Solicitud y Despacho
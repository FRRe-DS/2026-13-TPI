# RF-5.1 – Solicitud de viaje inmediato

## 1. Descripción

Este requerimiento permite al cliente solicitar un viaje inmediato
indicando el origen, el destino y el tipo de vehículo.

También permite consultar una tarifa estimada antes de confirmar
la solicitud.

La implementación se basa en el contrato OpenAPI v1.5.3 del módulo M5.

## 2. Tecnologías utilizadas

- Python.
- FastAPI.
- SQLAlchemy.
- MySQL.
- Pydantic.
- HTTPX.
- Keycloak y JWT.
- Docker.
- Pytest.

## 3. Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /api/v1/solicitudes/estimacion | Consultar tarifa estimada |
| POST | /api/v1/solicitudes | Registrar una solicitud inmediata |

## 4. Flujo de funcionamiento

### Estimación del viaje

1. Se valida la identidad del cliente.
2. Se consulta a M4 la distancia y duración del trayecto.
3. Se solicita a M7 el cálculo de la tarifa.
4. Se devuelve el importe estimado al cliente.

La estimación no genera una solicitud en la base de datos.

### Registro de la solicitud

1. Se valida el token JWT del cliente.
2. Se obtiene su identificador mediante el claim sub.
3. Se verifica la clave de idempotencia.
4. Se consulta a M2 el estado de la cuenta.
5. Se registra la solicitud en MySQL.
6. Se registra y procesa el evento VIAJE_SOLICITADO para M8.
7. Se devuelve la solicitud con estado pendiente.
8. Se inicia RF-5.3 en segundo plano.

## 5. Integraciones

| Módulo | Responsabilidad | Comunicación |
|--------|-----------------|--------------|
| M1 | Autenticación y autorización | JWT / HTTP |
| M2 | Validación del estado del cliente | HTTP REST |
| M4 | Estimación de distancia y duración | HTTP REST |
| M7 | Cálculo de tarifa estimada | HTTP REST |
| M8 | Notificación al cliente | HTTP REST |

La conexión con RF-5.3 se realiza reutilizando el servicio interno
iniciar_busqueda(), sin realizar peticiones HTTP dentro de M5.

## 6. Idempotencia

El endpoint de creación requiere el encabezado Idempotency-Key.

- Una solicitud nueva devuelve HTTP 201.
- Una petición repetida con la misma clave y los mismos datos
  devuelve HTTP 200.
- La reutilización de una clave con datos diferentes devuelve HTTP 409.
- Una clave ausente o inválida devuelve HTTP 400.

La base de datos cuenta con una restricción de unicidad sobre
cliente_id e idempotency_key para evitar registros duplicados.

## 7. Notificaciones

Al registrar una solicitud se genera el evento VIAJE_SOLICITADO.

El evento se almacena en MySQL junto con la solicitud, dentro
de una misma transacción.

La notificación al cliente contempla los canales PUSH y EMAIL.

Ante errores temporales de comunicación con M8:

- Se conserva el identificador y el contenido original del evento.
- Se realizan hasta tres intentos en total.
- Se utiliza un intervalo mínimo de 60 segundos.
- Se respeta el encabezado Retry-After cuando corresponde.
- Los errores definitivos se registran como ERROR_INTEGRACION.

Un fallo de M8 no revierte el registro de la solicitud.

Si M8 no está configurado, no se consumen intentos de envío.

## 8. Variables de entorno

Configurar las siguientes variables en el archivo .env:

| Variable | Descripción |
|----------|-------------|
| KEYCLOAK_ISSUER | URL del realm de Keycloak |
| KEYCLOAK_AUDIENCE | Audiencia esperada del token |
| KEYCLOAK_CLIENT_ID | Identificador del servicio M5 |
| KEYCLOAK_CLIENT_SECRET | Credencial del servicio M5 |
| M2_URL | URL base del módulo M2 |
| M4_URL | URL base del módulo M4 |
| M7_URL | URL base del módulo M7 |
| M8_URL | URL base del módulo M8 |

Las credenciales reales no deben subirse al repositorio.

Las URLs deben ser accesibles desde el entorno donde se ejecuta M5.

## 9. Cambios en la base de datos

### Tabla solicitudes

Se incorporaron los siguientes campos durante la actualización
del modelo:

- idempotency_key
- request_hash
- reserva_id
- cliente_email
- fecha_asignacion
- conductor_id

También se incorporó una restricción de unicidad sobre
cliente_id e idempotency_key.

Para actualizar una base de datos existente, verificar primero
su estructura:

```sql
DESCRIBE solicitudes;
SHOW INDEX FROM solicitudes;
```

Ejecutar únicamente las modificaciones que todavía no se
encuentren aplicadas:

```sql
ALTER TABLE solicitudes
ADD COLUMN idempotency_key VARCHAR(128) NULL;

ALTER TABLE solicitudes
ADD COLUMN request_hash VARCHAR(64) NULL;

ALTER TABLE solicitudes
ADD COLUMN reserva_id VARCHAR(36) NULL UNIQUE;

ALTER TABLE solicitudes
ADD COLUMN cliente_email VARCHAR(255) NULL;

ALTER TABLE solicitudes
ADD COLUMN fecha_asignacion DATETIME NULL;

ALTER TABLE solicitudes
ADD COLUMN conductor_id VARCHAR(36) NULL;

ALTER TABLE solicitudes
ADD CONSTRAINT uq_cliente_idempotencia
UNIQUE (cliente_id, idempotency_key);
```

No es necesario eliminar los datos existentes.

### Tabla eventos_notificacion

Se incorporó una tabla para almacenar las notificaciones
generadas por M5.

Sus campos principales son:

- evento_id
- solicitud_id
- tipo
- cuerpo
- estado
- intentos
- fecha_creacion
- fecha_envio
- proximo_intento

Los estados internos de una notificación son:

- PENDIENTE
- ENVIADO
- ERROR

Para crear la tabla desde el modelo de SQLAlchemy:

```bash
docker compose exec api python -c "from app.database import engine; from app.models.evento_notificacion import EventoNotificacion; EventoNotificacion.__table__.create(bind=engine, checkfirst=True)"
```

Si la tabla ya existe, verificar su estructura:

```sql
DESCRIBE eventos_notificacion;
```

En caso de que no exista la columna proximo_intento:

```sql
ALTER TABLE eventos_notificacion
ADD COLUMN proximo_intento DATETIME NULL;
```

## 10. Ejecución

Construir e iniciar los contenedores:

```bash
docker compose up -d --build
```

Verificar su estado:

```bash
docker compose ps
```

Consultar los registros de la API:

```bash
docker compose logs --tail=50 api
```

La documentación interactiva está disponible en:

http://localhost:8000/docs

## 11. Pruebas

Ejecutar las pruebas específicas de RF-5.1:

```bash
python -m pytest tests/test_rf_5_1.py -v
```

Resultado obtenido durante el desarrollo:

18 pruebas aprobadas.

Las pruebas verifican:

- Estado de cuenta del cliente.
- Registro de solicitudes.
- Validación de datos.
- Idempotencia.
- Estimación de tarifa.
- Persistencia de notificaciones.
- Manejo de errores de M8.
- Límite de reintentos.
- Inicio de RF-5.3 sin duplicar búsquedas.

Las pruebas utilizan SQLite y respuestas simuladas de los
módulos externos.

## 12. Consideraciones para la integración

- Confirmar los roles y la audiencia de los tokens de M1.
- Configurar las direcciones reales de los módulos externos.
- Verificar las comunicaciones entre módulos.
- Comprobar la concurrencia sobre MySQL.
- Revisar el formato de errores respecto al contrato OpenAPI.
- Adaptar las pruebas grupales al prefijo /api/v1.
- Coordinar la continuidad entre búsqueda y generación de ofertas.

La búsqueda en segundo plano utiliza BackgroundTasks de FastAPI.
Actualmente no contempla la recuperación automática de tareas
ante una caída del servidor.

## 13. Estado de implementación

- RF-5.1 implementado.
- 18 pruebas específicas aprobadas.
- Inicio de la API en Docker verificado.
- Endpoints disponibles en Swagger.
- Integración real con los demás módulos pendiente de validación.
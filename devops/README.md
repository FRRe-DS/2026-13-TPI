# devops/ — aporte del equipo DevOps (Grupo 5) a M5 G13

Esta carpeta y `.github/workflows/ci.yml` son el aporte del equipo DevOps del TP Integrador
Intercátedra. **No modifican la lógica funcional del módulo**: agregan CI, pruebas E2E,
análisis de seguridad y la bitácora del trabajo conjunto. Todo cambio entra por Pull Request
y lo revisa el grupo G13.

La misma estructura existe en el repo de G04 (consorcio A): los dos repos implementan M5 y se
gestionan con el mismo contrato, para poder comparar las dos implementaciones.

```
.github/workflows/ci.yml       pipeline de CI
devops/
├── bitacora.md                bitácora compartida DevOps <-> Desarrollo (igual en G04 y G13)
├── ci/
│   ├── junit_summary.py       resumen de tests (JUnit) en la página de la ejecución
│   ├── sarif_gate.py          Quality Gate de SAST sobre los resultados de CodeQL
│   └── m1_tokens_prueba.py    reemplazo de Keycloak en el CI: clave y tokens de prueba
├── k6/
│   ├── e2e.js                 flujo E2E (igual en G04 y G13)
│   └── lib/
│       ├── api.js             adaptador de la API de G13 (lo único que cambia entre repos)
│       └── mocks.js           consultas al mock para verificar las llamadas a otros módulos
└── mocks/mappings/            mocks de M1, M2, M4 y M8 (WireMock) armados desde los contratos oficiales
```

## Pipeline (`ci.yml`)

Se ejecuta al **abrir o actualizar un PR hacia `main`**, en cada **push a `main`** y a mano
(*Run workflow*).

| Job | Qué verifica | Si falla |
|---|---|---|
| `build` | `pip install`, compilación y que `app.main` cargue | Bloquea `unit-tests`, `e2e` y `docker` |
| `unit-tests` | `pytest` (SQLite, como hoy). Publica el resumen y el reporte JUnit | Falla si algún test falla |
| `e2e` | La app con **MySQL 8.4 real** y **mocks de M1, M2, M4 y M8**, recorrida con **k6** | Falla si alguna verificación falla |
| `sast` | **CodeQL** (`security-extended`) + Quality Gate | Falla con alertas **altas o críticas** |
| `secrets` | **gitleaks** sobre el árbol actual y los commits nuevos | Falla si encuentra un secreto |
| `docker` | Build de la imagen con el `Dockerfile` actual (no se publica) | Falla si no construye |

Los resultados quedan en la pestaña *Actions*: el resumen de cada job y los artefactos (JUnit,
reportes k6, SARIF). Las alertas de CodeQL también aparecen en *Security → Code scanning*.

### Quality Gate de SAST

- **Bloquean** el PR las alertas con *security-severity* ≥ 7.0 (**altas** y **críticas**).
- Las **medias** y **bajas** se informan en el resumen sin bloquear.
- El umbral se cambia en un solo lugar: `--umbral` en el job `sast`.

### E2E

El flujo está en `devops/k6/e2e.js`. Corre con 1 usuario virtual: es una verificación funcional,
no una prueba de carga. El mismo script es la base de los escenarios de carga del Hito 3.

1. **Solicitud inmediata (RF-5.1):** sin token 401, token sin rol `CLIENTE` 403, sin
   `Idempotency-Key` 400; con token, 201 con el cliente tomado del token. La misma clave devuelve
   la misma solicitud (200) y con otros datos da 409. En el mock se verifica que M5 consultó a M2
   una sola vez, que avisó a M8 (`VIAJE_SOLICITADO`) y que disparó sola la búsqueda en M4.
2. **Solicitud desde reserva (RF-5.2) y búsqueda (RF-5.3):** la misma reserva devuelve la misma
   solicitud; la búsqueda trae los 2 candidatos de M4 filtrados y ordenados; repetirla da 409.
3. Sin conductores disponibles → `sin_disponibilidad`.
4. M4 no disponible → M5 responde 503: un error de M4 no se toma como lista vacía.
5. **Cancelación previa (RF-5.7):** cliente ajeno 403, dueño 200, segunda cancelación 409,
   búsqueda sobre una cancelada 409.

**Pendiente:** cuando RF-5.5 esté en `main`, sumar la generación de ofertas y **dos aceptaciones
simultáneas**, para verificar que una sola gana (RNF-08).

### Mocks de los módulos dependientes

Un único WireMock atiende a todos los módulos, cada uno en sus rutas del contrato oficial
(`2026-TPI/contratos/`):

| Módulo | Ruta | Respuesta |
|---|---|---|
| M1 (Keycloak) | `POST /realms/{realm}/protocol/openid-connect/token` | Token de servicio de M5 |
| M1 (Keycloak) | `GET /realms/{realm}/protocol/openid-connect/certs` | Clave pública (la genera `m1_tokens_prueba.py` en cada corrida) |
| M2 | `GET /api/v1/clientes/{id}/estado-cuenta` | `ACTIVO` |
| M4 | `GET /api/v1/conductores/cercanos` | `AUTO`: 2 candidatos · `MOTO`: lista vacía · `origen_latitud=-27.0`: 503 |
| M8 | `POST /api/v1/eventos` | 202 |

Los tokens de cliente los firma `devops/ci/m1_tokens_prueba.py` con una clave RSA que se genera
en cada corrida y se descarta al terminar: no hay secretos en el repo.

## Correrlo localmente

Requiere Docker y Python con las dependencias del proyecto. Desde la raíz del repo:

```bash
# MySQL y mocks
docker run -d --name ci-mysql -p 13306:3306 -e MYSQL_ROOT_PASSWORD=root_ci \
  -e MYSQL_DATABASE=m5_db -e MYSQL_USER=m5_user -e MYSQL_PASSWORD=m5_ci mysql:8.4
docker run -d --name mocks -p 8089:8080 -v "$PWD/devops/mocks:/home/wiremock:ro" wiremock/wiremock:3.13.2

# Variables de M5 (los módulos dependientes apuntan a los mocks)
export MYSQL_HOST=127.0.0.1 MYSQL_PORT=13306 MYSQL_USER=m5_user MYSQL_PASSWORD=m5_ci MYSQL_DATABASE=m5_db \
       KEYCLOAK_ISSUER=http://127.0.0.1:8089/realms/ds-2026-realm KEYCLOAK_AUDIENCE=grupo-13 \
       KEYCLOAK_CLIENT_ID=grupo-13 KEYCLOAK_CLIENT_SECRET=descartable-ci \
       M2_URL=http://127.0.0.1:8089 M4_URL=http://127.0.0.1:8089 M4_BASE_URL=http://127.0.0.1:8089 \
       M7_URL=http://127.0.0.1:8089 M8_URL=http://127.0.0.1:8089

# Tokens de prueba y M5 (esperar a que MySQL esté listo)
python devops/ci/m1_tokens_prueba.py --mock http://127.0.0.1:8089 > /tmp/m5-tokens.env
python crear_tablas.py
uvicorn app.main:app --host 0.0.0.0 --port 18000 &

# E2E
docker run --rm --add-host=host.docker.internal:host-gateway --env-file /tmp/m5-tokens.env \
  -v "$PWD/devops/k6:/scripts:ro" grafana/k6:2.4.0 \
  run -e BASE_URL=http://host.docker.internal:18000 -e MOCKS_URL=http://host.docker.internal:8089 /scripts/e2e.js

# Limpieza
docker rm -f ci-mysql mocks; rm /tmp/m5-tokens.env
```

Las credenciales de MySQL de arriba y del workflow son **descartables**: la base solo existe
mientras dura la prueba. Las credenciales reales nunca van al repo (RNF-06).

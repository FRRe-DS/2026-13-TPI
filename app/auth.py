import os
import jwt
import httpx

from jwt import PyJWKClient
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE")
# Credenciales de M5 para autenticarse ante Keycloak.
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")

security = HTTPBearer(auto_error=False)

#Esta función verifica la autenticidad y vigencia del token y devuelve sus datos.
def validar_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token requerido")

    if not KEYCLOAK_ISSUER or not KEYCLOAK_AUDIENCE:
        raise HTTPException(status_code=503, detail="M1 no configurado")

    try:
        jwks_url = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
        jwks_client = PyJWKClient(jwks_url)

        token = credentials.credentials
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER,
            options={"require": ["exp", "sub"]}
        )

    except jwt.PyJWKClientConnectionError:
        raise HTTPException(status_code=503, detail="M1 no disponible")

    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

def validar_cliente(payload: dict = Depends(validar_token)):
    # Obtiene los roles del usuario desde el JWT.
    roles = payload.get("realm_access", {}).get("roles", [])

    # Solo los usuarios con rol CLIENTE pueden solicitar viajes.
    if "CLIENTE" not in roles:
        raise HTTPException(
            status_code=403,
            detail="El usuario no tiene permisos para solicitar viajes"
        )

    return payload

def obtener_token_servicio():
    # Verifica que las credenciales estén configuradas.
    if not all([KEYCLOAK_ISSUER, KEYCLOAK_CLIENT_ID,
                KEYCLOAK_CLIENT_SECRET]):
        raise HTTPException(503, "M1 no configurado")

    # Solicita un JWT propio de M5 mediante Client Credentials.
    try:
        respuesta = httpx.post(
            f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET
            },
            timeout=5.0
        )
        respuesta.raise_for_status()

        # Recupera el token entregado por Keycloak.
        return respuesta.json()["access_token"]

    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(503, "No se pudo obtener el token de M5")
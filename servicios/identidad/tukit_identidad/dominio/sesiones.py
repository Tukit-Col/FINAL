"""Autenticacion y sesion: convierte un correo y una clave en un token con roles.

Decisiones:
- La clave se hashea con PBKDF2-HMAC-SHA256 de la biblioteca estandar, con sal por usuario, porque
  la integracion continua no instala `argon2-cffi` ni `passlib`. `verificar_clave` reconoce el
  algoritmo por su prefijo, asi que subir el costo no obliga a reescribir a nadie.
- Los roles salen de `AsignacionRol` resueltos con `roles_vigentes`, y el token lleva la
  `version_permisos` que el gateway compara para revocar.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from tukit_comun.entorno import exigir_en_produccion

VARIABLE_LLAVE = "TUKIT_LLAVE_SESION"
# En produccion la llave firma todas las sesiones: corta, se adivina.
_LARGO_MINIMO_PRODUCCION = 32
_LLAVE_DESARROLLO = "tukit-desarrollo-no-usar-en-produccion"

VIDA_SEGUNDOS = 8 * 60 * 60

_ITERACIONES_PBKDF2 = 240_000
_ALGORITMO = "pbkdf2_sha256"


def hashear_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, _ITERACIONES_PBKDF2)
    return "$".join(
        [
            _ALGORITMO,
            str(_ITERACIONES_PBKDF2),
            base64.b64encode(sal).decode("ascii"),
            base64.b64encode(derivado).decode("ascii"),
        ]
    )


def verificar_clave(clave: str, guardado: str) -> bool:
    try:
        algoritmo, crudo_iter, crudo_sal, crudo_hash = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != _ALGORITMO:
        return False
    try:
        sal = base64.b64decode(crudo_sal)
        esperado = base64.b64decode(crudo_hash)
        iteraciones = int(crudo_iter)
    except (ValueError, TypeError):
        return False
    derivado = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones)
    return hmac.compare_digest(derivado, esperado)


def _llave() -> bytes:
    cruda = os.environ.get(VARIABLE_LLAVE, "").strip()
    exigir_en_produccion(
        len(cruda) >= _LARGO_MINIMO_PRODUCCION and cruda != _LLAVE_DESARROLLO,
        f"{VARIABLE_LLAVE} falta, es la de desarrollo o tiene menos de {_LARGO_MINIMO_PRODUCCION} "
        "caracteres; cualquiera podria firmar una sesion.",
    )
    if not cruda:
        print(
            f"[sesiones] {VARIABLE_LLAVE} no esta puesta: los tokens se firman con "
            "una llave de DESARROLLO conocida. No sirve para produccion."
        )
        cruda = _LLAVE_DESARROLLO
    return cruda.encode("utf-8")


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _desb64(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def emitir_token(usuario_id: uuid.UUID, version_permisos: int, ahora: float | None = None) -> str:
    momento = time.time() if ahora is None else ahora
    payload = {
        "sub": str(usuario_id),
        "vp": int(version_permisos),
        "exp": int(momento + VIDA_SEGUNDOS),
    }
    cuerpo = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    firma = _b64(hmac.new(_llave(), cuerpo.encode("ascii"), hashlib.sha256).digest())
    return f"{cuerpo}.{firma}"


def leer_token(token: str, ahora: float | None = None) -> dict | None:
    try:
        cuerpo, firma = token.split(".")
    except ValueError:
        return None
    esperada = _b64(hmac.new(_llave(), cuerpo.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(firma, esperada):
        return None
    try:
        payload = json.loads(_desb64(cuerpo).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    momento = time.time() if ahora is None else ahora
    if not isinstance(payload, dict) or "exp" not in payload:
        return None
    if float(payload["exp"]) < momento:
        return None
    return payload

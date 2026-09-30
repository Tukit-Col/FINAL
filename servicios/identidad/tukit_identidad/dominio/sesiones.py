"""Autenticacion y sesion: convierte un correo+clave en un token con roles.

Es "el registro de verdad" que el docstring de `registrar_contacto` ya
anticipaba: hasta hoy un usuario nacia sin credencial utilizable
(`clave_hash="sin-credencial"`) porque el flujo solo lo necesitaba como
destinatario del aviso. Aqui se agrega lo que faltaba para que el frontend
pueda entrar y ser enrutado por rol (ADR 0008), SIN salirse de lo que
Identidad ya sabe hacer: los roles salen de `AsignacionRol` resueltos con
`roles_vigentes`, y el token lleva la `version_permisos` que el gateway
compara para revocar (ADR 0016).

Dos decisiones, ambas con el mismo criterio que `cifrado.py`: no fingir una
garantia que no se tiene.

- **La clave se hashea con PBKDF2 de la stdlib**, no con Argon2/bcrypt. Es
  deliberado: la integracion continua no instala `argon2-cffi` ni `passlib`,
  igual que no instala `cryptography`. PBKDF2-HMAC-SHA256 con sal por usuario
  es lo correcto de la biblioteca estandar; el dia que se quiera subir el
  costo, `verificar_clave` reconoce el algoritmo por su prefijo y se puede
  migrar sin reescribir a nadie.
- **El token se firma con HMAC** y una llave del entorno. Si la llave no esta,
  se usa una de desarrollo y SE AVISA en cada arranque, para que un token de
  produccion no dependa por accidente de un secreto conocido. No es un JWT con
  libreria externa: es `base64url(payload).firma`, verificable con la stdlib,
  y el gateway lo comprueba sin importar codigo de Identidad.
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

VARIABLE_LLAVE = "TUKIT_LLAVE_SESION"
# Solo para desarrollo. Si el token de un entorno real cuelga de esto, es un
# error de despliegue, y por eso se grita al arrancar (ver `_llave`).
_LLAVE_DESARROLLO = "tukit-desarrollo-no-usar-en-produccion"

# Vida del token. Corta a proposito: el acudiente entra por temporada, no vive
# logueado. El gateway igual puede revocar antes comparando `version_permisos`.
VIDA_SEGUNDOS = 8 * 60 * 60

_ITERACIONES_PBKDF2 = 240_000
_ALGORITMO = "pbkdf2_sha256"


# --------------------------------------------------------------------- claves


def hashear_clave(clave: str) -> str:
    """`pbkdf2_sha256$iteraciones$sal$hash`, todo en una cadena portable.

    El formato con prefijo es lo que permite cambiar de algoritmo mas adelante
    sin una migracion: `verificar_clave` mira el prefijo y sabe como comparar.
    """
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
    """Compara en tiempo constante. Un centinela no valida contra nada.

    `clave_hash="sin-credencial"` (el valor con que nace un contacto sin
    registro) no tiene el prefijo del algoritmo, asi que cae aqui como `False`:
    una cuenta de invitado no puede iniciar sesion, que es justo lo que se
    quiere.
    """
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


# --------------------------------------------------------------------- tokens


def _llave() -> bytes:
    cruda = os.environ.get(VARIABLE_LLAVE, "").strip()
    if not cruda:
        # Mismo espiritu que `CifradorEnClaro`: corre en desarrollo y se nota.
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
    """`base64url(payload).firma`. El payload lleva lo justo para revocar.

    Va `usuario_id` y `version_permisos` (para que el gateway pueda comparar
    sin consultar Identidad en cada peticion, ADR 0016) y `exp` (para caducar).
    NO va el correo ni ningun rol: los roles se resuelven contra la base al
    validar la sesion, que es donde estan siempre al dia.
    """
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
    """Verifica firma y expiracion. Devuelve el payload, o `None` si no vale.

    Falla CERRADA: una firma que no cuadra, un token vencido o uno con forma
    rara no lanzan, devuelven `None`, y quien llama trata eso como "sin sesion".
    """
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

"""El limite de tasa de la puerta (ADR 0047).

Dos niveles, y en cada uno dos claves que tienen que pasar las dos:

- **General**, todo `/v1/*`: 300 por token y 1.200 por IP cada 60 s.
- **Estricto**, por ruta, en las que cuestan (leer un PDF, crear un trabajo,
  derivar una clave): 30 por token y 60 por IP cada 600 s. Una ruta estricta
  cuenta tambien en el general, y cada una tiene su propio cupo: los intentos de
  entrar no gastan el de las subidas.

La IP tiene mas cupo que el token porque detras de una IP puede haber muchas
familias (un colegio, el NAT de un operador movil). Sin token solo cuenta la IP;
con un token inventado en cada peticion tambien, asi que inventarlos no da cupo.

**La IP del cliente.** Si la conexion viene de un proxy de confianza
(`TUKIT_PROXIES_CONFIANZA`; por omision `127.0.0.1,::1`, que es donde corre la
web), se recorre `X-Forwarded-For` de derecha a izquierda y la IP es la primera
que no es de confianza. Si no viene de uno, la cabecera se ignora: la escribio
el cliente. Esta regla es la unica: `api.main` lanza uvicorn sin
`proxy_headers`, porque uvicorn confia en 127.0.0.1 por su lado y reescribiria
la conexion antes de que el limite la vea.

**El conteo** es por ventana fija, en Redis si responde y en la memoria del
proceso si no (`tukit_comun.cache`). Las claves llevan el SHA-256 del token y
el de la IP, nunca uno ni otra en claro, y no salen en ningun log.

Quedan fuera `/v1/servicios`, `/v1/webhooks/*` (la pasarela no reintenta un
429 como una familia), las preflight `OPTIONS` y lo que no es `/v1/*`. Una ruta
desconocida si cuenta: un escaner tambien gasta cupo.
"""

from __future__ import annotations

import functools
import hashlib
import ipaddress
import logging
import math
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from tukit_comun import metricas
from tukit_comun.cache import cliente_redis, entero_de_entorno

log = logging.getLogger(__name__)

PROXIES_POR_OMISION = "127.0.0.1,::1"

# (nombre en la clave, ruta) de las estrictas; solo cuentan con POST.
RUTAS_ESTRICTAS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("listas-subir", re.compile(r"/v1/listas/subir")),
    ("trabajos", re.compile(r"/v1/trabajos")),
    ("trabajos-reintentar", re.compile(r"/v1/trabajos/[^/]+/reintentar")),
    ("trabajos-aplicar-canonico", re.compile(r"/v1/trabajos/aplicar-canonico")),
    ("onboarding", re.compile(r"/v1/admin/onboarding")),
    ("onboarding-preview", re.compile(r"/v1/admin/onboarding/[^/]+/preview")),
    ("sesiones", re.compile(r"/v1/sesiones")),
    ("cuenta", re.compile(r"/v1/cuenta")),
    ("registro", re.compile(r"/v1/registro")),
    ("catalogo-emparejar", re.compile(r"/v1/catalogo/emparejar")),
    # La sugerencia del acudiente sube un archivo sin sesion: misma cuenta que
    # una lista subida, no la general de lectura.
    ("sugerencias", re.compile(r"/v1/admin/sugerencias")),
)

Red = ipaddress.IPv4Network | ipaddress.IPv6Network
Ip = ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass(frozen=True)
class Nivel:
    nombre: str
    ventana: int
    por_token: int
    por_ip: int


@dataclass(frozen=True)
class Cuenta:
    """Una clave que se cuenta en esta peticion."""

    clave: str
    ventana: int
    tope: int
    nivel: str
    ruta: str
    tipo: str

    def __str__(self) -> str:
        # Lo que sale en el log: sin la huella.
        return f"{self.nivel}:{self.ruta}:{self.tipo}"


_VARIABLES = tuple(
    f"TUKIT_LIMITE_{nivel}_{campo}"
    for nivel in ("GENERAL", "ESTRICTO")
    for campo in ("VENTANA", "TOKEN", "IP")
)


def niveles() -> tuple[Nivel, Nivel]:
    """El general y el estricto, del entorno; un `0` apaga esa ventana o ese tope."""
    return _niveles(tuple(os.environ.get(variable, "") for variable in _VARIABLES))


@functools.cache
def _niveles(_crudos: tuple[str, ...]) -> tuple[Nivel, Nivel]:
    # Se arma una vez por cada combinacion del entorno: un valor mal escrito
    # deja un WARNING, no uno por peticion.
    def nivel(nombre: str, ventana: int, por_token: int, por_ip: int) -> Nivel:
        prefijo = f"TUKIT_LIMITE_{nombre.upper()}_"
        return Nivel(
            nombre=nombre,
            ventana=entero_de_entorno(prefijo + "VENTANA", ventana),
            por_token=entero_de_entorno(prefijo + "TOKEN", por_token),
            por_ip=entero_de_entorno(prefijo + "IP", por_ip),
        )

    return nivel("general", 60, 300, 1200), nivel("estricto", 600, 30, 60)


def proxies_de_confianza() -> tuple[Red, ...]:
    return _redes(os.environ.get("TUKIT_PROXIES_CONFIANZA", PROXIES_POR_OMISION))


@functools.cache
def _redes(crudo: str) -> tuple[Red, ...]:
    redes: list[Red] = []
    for entrada in (e.strip() for e in crudo.split(",")):
        if not entrada:
            continue
        try:
            redes.append(ipaddress.ip_network(entrada, strict=False))
        except ValueError:
            log.warning("TUKIT_PROXIES_CONFIANZA trae %r, que no es una IP ni una red: la ignoro", entrada)
    return tuple(redes)


def _ip(texto: str) -> Ip | None:
    try:
        ip = ipaddress.ip_address(texto.strip())
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def ip_del_cliente(conexion: str | None, reenviada: str | None, confianza: Sequence[Red]) -> str:
    """La IP del cliente: la de la conexion, o la de `X-Forwarded-For` si la
    conexion viene de un proxy de confianza."""
    directa = _ip(conexion or "")
    if directa is None:
        return conexion or "desconocida"

    def de_confianza(ip: Ip) -> bool:
        return any(ip in red for red in confianza)

    if not reenviada or not de_confianza(directa):
        return str(directa)
    ultima = directa
    for entrada in reversed([e for e in reenviada.split(",") if e.strip()]):
        ip = _ip(entrada)
        if ip is None:
            # Algo que no es una IP: lo que hay a su izquierda ya no se puede
            # creer. Se queda la ultima de confianza.
            break
        if not de_confianza(ip):
            return str(ip)
        ultima = ip
    return str(ultima)


def exenta(metodo: str, camino: str) -> bool:
    if metodo == "OPTIONS" or not camino.startswith("/v1/"):
        return True
    return camino == "/v1/servicios" or camino == "/v1/webhooks" or camino.startswith("/v1/webhooks/")


def ruta_estricta(metodo: str, camino: str) -> str | None:
    """El nombre de la ruta estricta de `metodo camino`, o `None`."""
    if metodo != "POST":
        return None
    camino = camino.rstrip("/")
    for nombre, patron in RUTAS_ESTRICTAS:
        if patron.fullmatch(camino):
            return nombre
    return None


def _token(autorizacion: str | None) -> str | None:
    if not autorizacion:
        return None
    esquema, _, token = autorizacion.strip().partition(" ")
    token = token.strip()
    return token if esquema.lower() == "bearer" and token else None


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def cuentas(metodo: str, camino: str, token: str | None, ip: str) -> list[Cuenta]:
    """Las claves que cuenta una peticion; vacia si esta exenta."""
    if exenta(metodo, camino):
        return []
    general, estricto = niveles()
    por_nivel = [(general, "v1")]
    estricta = ruta_estricta(metodo, camino)
    if estricta is not None:
        por_nivel.append((estricto, estricta))
    salida: list[Cuenta] = []
    for nivel, ruta in por_nivel:
        if nivel.ventana <= 0:
            continue
        for tipo, valor, tope in (("token", token, nivel.por_token), ("ip", ip, nivel.por_ip)):
            if valor is not None and tope > 0:
                clave = f"limite:{nivel.nombre}:{ruta}:{tipo}:{_huella(valor)}"
                salida.append(Cuenta(clave, nivel.ventana, tope, nivel.nombre, ruta, tipo))
    return salida


def mensaje(segundos: int) -> str:
    if segundos < 60:
        espera = "1 segundo" if segundos == 1 else f"{segundos} segundos"
    else:
        minutos = math.ceil(segundos / 60)
        espera = "1 minuto" if minutos == 1 else f"{minutos} minutos"
    return f"Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en {espera}."


def demasiadas(segundos: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": "demasiadas_peticiones",
            "mensaje": mensaje(segundos),
            "reintentar_en_segundos": segundos,
        },
        headers={"Retry-After": str(segundos)},
    )


async def revisar(peticion: Request, camino: str) -> JSONResponse | None:
    """El 429 si la peticion pasa de algun tope; `None` si puede seguir."""
    conexion = peticion.client.host if peticion.client else None
    reenviada = ", ".join(peticion.headers.getlist("x-forwarded-for")) or None
    ip = ip_del_cliente(conexion, reenviada, proxies_de_confianza())
    por_contar = cuentas(peticion.method, camino, _token(peticion.headers.get("authorization")), ip)
    if not por_contar:
        return None
    contadas = await cliente_redis().contar([(c.clave, c.ventana) for c in por_contar])
    pasadas = [(c, resta) for c, (cuenta, resta) in zip(por_contar, contadas, strict=True) if cuenta > c.tope]
    if not pasadas:
        return None
    segundos = max(1, max(math.ceil(resta / 1000) for _, resta in pasadas))
    for nivel in sorted({c.nivel for c, _ in pasadas}):
        metricas.contar_limite_rechazado(nivel)
    log.info("429 por %s", ", ".join(str(c) for c, _ in pasadas))
    return demasiadas(segundos)

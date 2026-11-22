"""Limite de tasa del gateway.

Decisiones:
- Tres niveles, y en cada uno deben pasar las dos claves (token e IP): general para todo `/v1/*`
  (300 por token y 1.200 por IP cada 60 s), estricto por ruta en las que cuestan (leer un PDF,
  crear un trabajo, derivar una clave: 30 por token y 60 por IP cada 600 s) y supresion para
  `POST /v1/cuenta/supresion` (5 por token y 10 por IP cada hora). Una ruta estricta cuenta tambien
  en el general y tiene su propio cupo.
- La IP tiene mas cupo que el token porque detras de una IP puede haber muchas familias. Sin token
  cuenta solo la IP; un token inventado en cada peticion tambien, asi que inventarlos no da cupo.
- La IP del cliente sale de `X-Forwarded-For`, de derecha a izquierda, solo si la conexion viene de
  un proxy de confianza (`TUKIT_PROXIES_CONFIANZA`); si no, la cabecera se ignora.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import math
import os
import re
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from tukit_comun import metricas
from tukit_comun.cache import cliente_redis, entero_de_entorno
from tukit_comun.red import ip_del_cliente, proxies_de_confianza

log = logging.getLogger(__name__)

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
    ("sugerencias", re.compile(r"/v1/admin/sugerencias")),
    ("nl2c", re.compile(r"/v1/nl2c/(?:interpretar|decision)")),
    ("nl2c-kit", re.compile(r"/v1/kits/[^/]+/asistente/proponer")),
    ("cuenta-supresion", re.compile(r"/v1/cuenta/supresion")),
    ("cuenta-consentimientos", re.compile(r"/v1/cuenta/consentimientos/revocar")),
)

RUTAS_SUPRESION = frozenset({"cuenta-supresion"})


@dataclass(frozen=True)
class Nivel:
    nombre: str
    ventana: int
    por_token: int
    por_ip: int


@dataclass(frozen=True)
class Cuenta:

    clave: str
    ventana: int
    tope: int
    nivel: str
    ruta: str
    tipo: str

    def __str__(self) -> str:
        return f"{self.nivel}:{self.ruta}:{self.tipo}"


_VARIABLES = tuple(
    f"TUKIT_LIMITE_{nivel}_{campo}"
    for nivel in ("GENERAL", "ESTRICTO")
    for campo in ("VENTANA", "TOKEN", "IP")
)


def niveles() -> tuple[Nivel, Nivel]:
    return _niveles(tuple(os.environ.get(variable, "") for variable in _VARIABLES))


@functools.cache
def _niveles(_crudos: tuple[str, ...]) -> tuple[Nivel, Nivel]:
    def nivel(nombre: str, ventana: int, por_token: int, por_ip: int) -> Nivel:
        prefijo = f"TUKIT_LIMITE_{nombre.upper()}_"
        return Nivel(
            nombre=nombre,
            ventana=entero_de_entorno(prefijo + "VENTANA", ventana),
            por_token=entero_de_entorno(prefijo + "TOKEN", por_token),
            por_ip=entero_de_entorno(prefijo + "IP", por_ip),
        )

    return nivel("general", 60, 300, 1200), nivel("estricto", 600, 30, 60)


def nivel_supresion() -> Nivel:
    return _nivel_supresion(
        tuple(os.environ.get(f"TUKIT_LIMITE_SUPRESION_{c}", "") for c in ("VENTANA", "TOKEN", "IP"))
    )


@functools.cache
def _nivel_supresion(_crudos: tuple[str, ...]) -> Nivel:
    return Nivel(
        nombre="supresion",
        ventana=entero_de_entorno("TUKIT_LIMITE_SUPRESION_VENTANA", 3600),
        por_token=entero_de_entorno("TUKIT_LIMITE_SUPRESION_TOKEN", 5),
        por_ip=entero_de_entorno("TUKIT_LIMITE_SUPRESION_IP", 10),
    )


def exenta(metodo: str, camino: str) -> bool:
    if metodo == "OPTIONS" or not camino.startswith("/v1/"):
        return True
    return camino == "/v1/servicios" or camino == "/v1/webhooks" or camino.startswith("/v1/webhooks/")


def ruta_estricta(metodo: str, camino: str) -> str | None:
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
    if exenta(metodo, camino):
        return []
    general, estricto = niveles()
    por_nivel = [(general, "v1")]
    estricta = ruta_estricta(metodo, camino)
    if estricta is not None:
        por_nivel.append((nivel_supresion() if estricta in RUTAS_SUPRESION else estricto, estricta))
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

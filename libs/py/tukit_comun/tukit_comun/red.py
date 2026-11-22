from __future__ import annotations

import functools
import ipaddress
import logging
import os
from collections.abc import Sequence

log = logging.getLogger(__name__)

PROXIES_POR_OMISION = "127.0.0.1,::1"

Red = ipaddress.IPv4Network | ipaddress.IPv6Network
Ip = ipaddress.IPv4Address | ipaddress.IPv6Address


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
            break
        if not de_confianza(ip):
            return str(ip)
        ultima = ip
    return str(ultima)


def ip_de_peticion(conexion: str | None, cabeceras_reenviadas: Sequence[str]) -> str:
    return ip_del_cliente(conexion, ", ".join(cabeceras_reenviadas) or None, proxies_de_confianza())


__all__ = ["PROXIES_POR_OMISION", "Ip", "Red", "ip_de_peticion", "ip_del_cliente", "proxies_de_confianza"]

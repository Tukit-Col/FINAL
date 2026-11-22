"""Ensayo de carga de solo lectura contra el backend local (DP-02, DP-05)."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

HOSTS_PERMITIDOS = {"127.0.0.1", "localhost", "::1"}
IP_DE_PRUEBA = "203.0.113.77"
TIEMPO_MAXIMO_S = 10.0


@dataclass(frozen=True)
class Punto:

    nombre: str
    base: str
    ruta: str


@dataclass
class Muestra:
    inicio: float
    fin: float
    punto: str
    estado: int
    bytes: int


@dataclass
class Acumulado:
    muestras: list[Muestra] = field(default_factory=list)


def percentil(ordenados: list[float], p: float) -> float:
    if not ordenados:
        return math.nan
    rango = max(1, math.ceil(p / 100 * len(ordenados)))
    return ordenados[rango - 1]


def resumir(muestras: list[Muestra], duracion_s: float) -> dict:
    total = len(muestras)
    estados = Counter(m.estado for m in muestras)
    limitadas = estados.get(429, 0)
    exitosas = sum(n for e, n in estados.items() if 200 <= e < 300)
    errores = total - exitosas - limitadas
    buenas = sorted((m.fin - m.inicio) * 1000 for m in muestras if 200 <= m.estado < 300)
    return {
        "peticiones": total,
        "exitosas_2xx": exitosas,
        "limitadas_429": limitadas,
        "errores": errores,
        "tasa_error_pct": round(100 * errores / total, 3) if total else None,
        "tasa_429_pct": round(100 * limitadas / total, 3) if total else None,
        "estados": {str(e): n for e, n in sorted(estados.items())},
        "peticiones_por_s": round(total / duracion_s, 1) if duracion_s else None,
        "exitosas_por_s": round(exitosas / duracion_s, 1) if duracion_s else None,
        "latencia_ms": {
            "p50": round(percentil(buenas, 50), 2),
            "p95": round(percentil(buenas, 95), 2),
            "p99": round(percentil(buenas, 99), 2),
            "max": round(buenas[-1], 2) if buenas else math.nan,
        },
        "bytes_recibidos": sum(m.bytes for m in muestras),
    }


def _validar_local(url: str) -> None:
    anfitrion = urlparse(url).hostname
    if anfitrion not in HOSTS_PERMITIDOS:
        raise SystemExit(f"Solo se ensaya contra la maquina local; {url!r} no lo es.")


async def _usuario(
    puntos: list[Punto],
    acumulado: Acumulado,
    fin_total: float,
    cabeceras: dict[str, str],
    desfase: int,
) -> None:
    async with httpx.AsyncClient(timeout=TIEMPO_MAXIMO_S, headers=cabeceras) as cliente:
        i = desfase
        while time.perf_counter() < fin_total:
            punto = puntos[i % len(puntos)]
            i += 1
            inicio = time.perf_counter()
            estado, tamano = 0, 0
            try:
                respuesta = await cliente.get(punto.base + punto.ruta)
                estado, tamano = respuesta.status_code, len(respuesta.content)
            except httpx.HTTPError:
                pass
            acumulado.muestras.append(Muestra(inicio, time.perf_counter(), punto.nombre, estado, tamano))


async def correr_nivel(
    puntos: list[Punto], usuarios: int, duracion_s: float, calentamiento_s: float, cabeceras: dict[str, str]
) -> dict:
    acumulado = Acumulado()
    t0 = time.perf_counter()
    fin_total = t0 + calentamiento_s + duracion_s
    await asyncio.gather(*(_usuario(puntos, acumulado, fin_total, cabeceras, u) for u in range(usuarios)))
    desde = t0 + calentamiento_s
    medidas = [m for m in acumulado.muestras if m.inicio >= desde and m.fin <= fin_total]
    resultado = {"usuarios": usuarios, "duracion_s": duracion_s, "global": resumir(medidas, duracion_s)}
    resultado["por_endpoint"] = {
        p.nombre: resumir([m for m in medidas if m.punto == p.nombre], duracion_s) for p in puntos
    }
    return resultado


def hardware() -> dict:
    def sysctl(clave: str) -> str | None:
        try:
            return subprocess.run(
                ["sysctl", "-n", clave], capture_output=True, text=True, check=True, timeout=5
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None

    memoria = sysctl("hw.memsize")
    return {
        "cpu": sysctl("machdep.cpu.brand_string") or platform.processor(),
        "nucleos_logicos": sysctl("hw.ncpu"),
        "memoria_gb": round(int(memoria) / 2**30, 1) if memoria else None,
        "sistema": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "httpx": httpx.__version__,
        "nota": "Generador, servicios y Postgres comparten esta maquina.",
    }


def endpoints_capacidad(argumentos: argparse.Namespace) -> list[Punto]:
    return [
        Punto("grados-canonicos", argumentos.inteligencia, "/v1/grados-canonicos"),
        Punto("catalogo-productos", argumentos.catalogo, "/v1/catalogo/productos?limite=5"),
        Punto("catalogo-tiendas", argumentos.catalogo, "/v1/catalogo/tiendas"),
        Punto("trabajo-publicado", argumentos.inteligencia, f"/v1/trabajos/{argumentos.trabajo_id}"),
    ]


def endpoints_puerta(argumentos: argparse.Namespace) -> list[Punto]:
    return [
        Punto("grados-canonicos", argumentos.gateway, "/v1/grados-canonicos"),
        Punto("catalogo-productos", argumentos.gateway, "/v1/catalogo/productos?limite=5"),
        Punto("catalogo-tiendas", argumentos.gateway, "/v1/catalogo/tiendas"),
        Punto("trabajo-publicado", argumentos.gateway, f"/v1/trabajos/{argumentos.trabajo_id}"),
    ]


async def principal(argumentos: argparse.Namespace) -> dict:
    for url in (argumentos.gateway, argumentos.catalogo, argumentos.inteligencia):
        _validar_local(url)
    niveles = [int(n) for n in argumentos.niveles.split(",")]
    salida: dict = {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware(),
        "solo_lectura": True,
        "parametros": {
            "niveles_usuarios": niveles,
            "duracion_por_nivel_s": argumentos.duracion,
            "calentamiento_s": argumentos.calentamiento,
            "tiempo_maximo_peticion_s": TIEMPO_MAXIMO_S,
            "pausa_entre_peticiones": "ninguna (bucle cerrado)",
        },
    }
    if argumentos.modo in ("capacidad", "todo"):
        puntos = endpoints_capacidad(argumentos)
        niveles_resultado = []
        for n in niveles:
            print(f"[capacidad] {n} usuarios, {argumentos.duracion:g} s ...", flush=True)
            r = await correr_nivel(puntos, n, argumentos.duracion, argumentos.calentamiento, {})
            niveles_resultado.append(r)
            g = r["global"]
            print(
                f"    {g['peticiones_por_s']} req/s  p50={g['latencia_ms']['p50']} "
                f"p95={g['latencia_ms']['p95']} p99={g['latencia_ms']['p99']} ms "
                f"error={g['tasa_error_pct']} %",
                flush=True,
            )
            await asyncio.sleep(2)
        salida["capacidad"] = {
            "destino": "puertos de los servicios (sin gateway)",
            "endpoints": [{"nombre": p.nombre, "url": p.base + p.ruta} for p in puntos],
            "niveles": niveles_resultado,
        }
    if argumentos.modo in ("limite", "todo"):
        puntos = endpoints_puerta(argumentos)
        cabeceras = {"X-Forwarded-For": IP_DE_PRUEBA}
        print(
            f"[limite] {argumentos.usuarios_limite} usuarios, "
            f"{argumentos.duracion_limite:g} s por la puerta ...",
            flush=True,
        )
        r = await correr_nivel(puntos, argumentos.usuarios_limite, argumentos.duracion_limite, 0.0, cabeceras)
        salida["limite"] = {
            "destino": "gateway (puerto 8010) con X-Forwarded-For de documentacion",
            "ip_simulada": IP_DE_PRUEBA,
            "endpoints": [{"nombre": p.nombre, "url": p.base + p.ruta} for p in puntos],
            "resultado": r,
        }
        g = r["global"]
        print(f"    2xx={g['exitosas_2xx']} 429={g['limitadas_429']} errores={g['errores']}", flush=True)
    return salida


def leer_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    a = argparse.ArgumentParser(description="Ensayo de carga de solo lectura contra el backend local.")
    a.add_argument("--trabajo-id", required=True, help="Id de un trabajo publicado anonimo (ver README).")
    a.add_argument("--modo", choices=["capacidad", "limite", "todo"], default="todo")
    a.add_argument(
        "--niveles", default="1,5,10,20", help="Usuarios concurrentes por nivel, separados por coma."
    )
    a.add_argument("--duracion", type=float, default=30.0, help="Segundos medidos por nivel.")
    a.add_argument(
        "--calentamiento", type=float, default=3.0, help="Segundos descartados al inicio de cada nivel."
    )
    a.add_argument("--usuarios-limite", type=int, default=5)
    a.add_argument("--duracion-limite", type=float, default=15.0)
    a.add_argument("--gateway", default="http://127.0.0.1:8010")
    a.add_argument("--catalogo", default="http://127.0.0.1:8012")
    a.add_argument("--inteligencia", default="http://127.0.0.1:8013")
    a.add_argument("--salida", type=Path, default=None, help="Archivo JSON de resultados.")
    return a.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argumentos = leer_argumentos(argv)
    resultado = asyncio.run(principal(argumentos))
    if argumentos.salida:
        argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
        argumentos.salida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n")
        print(f"Resultados en {argumentos.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

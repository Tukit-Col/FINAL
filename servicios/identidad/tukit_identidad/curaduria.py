"""Los colegios de las listas curadas, de la base a git y de git a otra base.

Es la mitad de Identidad del modulo `curaduria` del Catalogo. Una lista curada
apunta a su colegio por `colegio_id`, y ese colegio vive aqui: si un compañero
importa la lista y no el colegio, la lista queda colgando de un colegio que su
Identidad no conoce y el acudiente nunca la encuentra.

Este servicio no lee la base del Catalogo (regla 3). Lee el ARCHIVO que el
Catalogo exporto, `datos/curaduria/listas_revisadas.csv`, para saber que
colegios hacen falta, y exporta solo esos:

- `datos/curaduria/colegios.csv`
- `datos/curaduria/sedes.csv`

Lo que NO viaja: `contacto_nombre`, `contacto_email` y `contacto_telefono`.
Son datos de una persona del colegio, y un repositorio no es donde deben vivir.

    python -m tukit_identidad.curaduria exportar
    python -m tukit_identidad.curaduria importar

`importar` usa la misma regla que el poller de `colegio_verificado`: un colegio
que no existe se crea con ESE identificador; uno que ya existe no se pisa, solo
se le completan los campos que tenia vacios.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .modelos import Colegio, Sede

RAIZ = Path(__file__).resolve().parents[3]
DATOS = RAIZ / "datos"

ARCHIVO_LISTAS = Path("curaduria") / "listas_revisadas.csv"
ARCHIVO_COLEGIOS = Path("curaduria") / "colegios.csv"
ARCHIVO_SEDES = Path("curaduria") / "sedes.csv"

# Los campos que se completan si estaban vacios, sin pisar lo que haya.
CAMPOS_PERFIL = ("nit", "dane", "logo_url", "sitio_web", "direccion")
COLUMNAS_COLEGIOS = ["id", "nombre", *CAMPOS_PERFIL]
COLUMNAS_SEDES = ["id", "colegio_id", "nombre"]


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def escribir_csv(ruta: Path, columnas: list[str], filas: list[dict[str, str]]) -> None:
    fin = "\r\n" if ruta.exists() and b"\r\n" in ruta.read_bytes()[:4096] else "\n"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator=fin)
        escritor.writeheader()
        escritor.writerows(filas)


def colegios_nombrados(filas_listas: list[dict[str, str]]) -> set[uuid.UUID]:
    return {uuid.UUID(f["colegio_id"]) for f in filas_listas}


async def exportar(
    db: AsyncSession, ids: set[uuid.UUID], previos: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    """Filas de colegios y sedes para `ids`. Devuelve (colegios, sedes, faltantes).

    Un colegio que la base local no tiene (el poller no ha corrido, o la lista
    vino de otro compañero y nadie importo sus colegios) conserva la fila que ya
    estaba en el CSV, si la habia: exportar no debe borrar lo que otro subio.
    """
    colegios = {c.id: c for c in (await db.execute(select(Colegio).where(Colegio.id.in_(ids)))).scalars()}
    sedes = (await db.execute(select(Sede).where(Sede.colegio_id.in_(ids)))).scalars().all()
    previos_por_id = {f["id"]: f for f in previos}

    filas_colegios: list[dict[str, str]] = []
    faltantes: list[str] = []
    for colegio_id in sorted(ids, key=str):
        colegio = colegios.get(colegio_id)
        if colegio is None:
            previo = previos_por_id.get(str(colegio_id))
            if previo is not None:
                filas_colegios.append(previo)
            else:
                faltantes.append(str(colegio_id))
            continue
        filas_colegios.append(
            {
                "id": str(colegio.id),
                "nombre": colegio.nombre,
                **{c: getattr(colegio, c) or "" for c in CAMPOS_PERFIL},
            }
        )
    filas_sedes = sorted(
        ({"id": str(s.id), "colegio_id": str(s.colegio_id), "nombre": s.nombre} for s in sedes),
        key=lambda f: (f["colegio_id"], f["nombre"], f["id"]),
    )
    return filas_colegios, filas_sedes, faltantes


async def importar(
    db: AsyncSession, colegios: list[dict[str, str]], sedes: list[dict[str, str]]
) -> tuple[int, int, int]:
    """Crea lo que falta y completa lo vacio. Devuelve (creados, completados, sedes)."""
    creados = completados = sedes_nuevas = 0
    for fila in colegios:
        colegio_id = uuid.UUID(fila["id"])
        existente = await db.get(Colegio, colegio_id)
        if existente is None:
            db.add(
                Colegio(
                    id=colegio_id,
                    nombre=fila["nombre"],
                    **{c: (fila.get(c) or None) for c in CAMPOS_PERFIL},
                )
            )
            creados += 1
            continue
        tocado = False
        for campo in CAMPOS_PERFIL:
            valor = fila.get(campo) or None
            if valor and getattr(existente, campo) is None:
                setattr(existente, campo, valor)
                tocado = True
        completados += tocado
    await db.flush()

    for fila in sedes:
        sede_id = uuid.UUID(fila["id"])
        if await db.get(Sede, sede_id) is None:
            db.add(Sede(id=sede_id, colegio_id=uuid.UUID(fila["colegio_id"]), nombre=fila["nombre"]))
            sedes_nuevas += 1
    await db.flush()
    return creados, completados, sedes_nuevas


async def _exportar(datos: Path) -> int:
    from tukit_comun.bd import crear_motor

    ids = colegios_nombrados(leer_csv(datos / ARCHIVO_LISTAS))
    motor = crear_motor("identidad")
    try:
        async with motor.sesion() as db:
            colegios, sedes, faltantes = await exportar(db, ids, leer_csv(datos / ARCHIVO_COLEGIOS))
    finally:
        await motor.cerrar()

    escribir_csv(datos / ARCHIVO_COLEGIOS, COLUMNAS_COLEGIOS, colegios)
    escribir_csv(datos / ARCHIVO_SEDES, COLUMNAS_SEDES, sedes)
    print("=== colegios de la curaduria ===")
    print(f"  colegios   {len(colegios):5}")
    print(f"  sedes      {len(sedes):5}")
    if faltantes:
        print(f"\n{len(faltantes)} colegio(s) de las listas no estan en Identidad (¿corrio el poller?):")
        for colegio_id in faltantes:
            print(f"  - {colegio_id}")
        return 1
    return 0


async def _importar(datos: Path) -> int:
    from tukit_comun.bd import crear_motor

    colegios = leer_csv(datos / ARCHIVO_COLEGIOS)
    sedes = leer_csv(datos / ARCHIVO_SEDES)
    motor = crear_motor("identidad")
    try:
        async with motor.sesion() as db:
            creados, completados, sedes_nuevas = await importar(db, colegios, sedes)
    finally:
        await motor.cerrar()

    print("=== colegios de la curaduria ===")
    print(f"  creados       {creados:5}")
    print(f"  completados   {completados:5}")
    print(f"  sedes nuevas  {sedes_nuevas:5}")
    return 0


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Exporta o importa los colegios de la curaduria.")
    analizador.add_argument("accion", choices=["exportar", "importar"])
    analizador.add_argument("--datos", type=Path, default=DATOS, help="la carpeta datos/ del repositorio")
    args = analizador.parse_args(argv)

    if args.accion == "exportar":
        return asyncio.run(_exportar(args.datos))
    return asyncio.run(_importar(args.datos))


if __name__ == "__main__":
    sys.exit(main())

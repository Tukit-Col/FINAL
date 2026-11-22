"""Siembra los colegios y sus sedes desde el CSV versionado del monorepo.

Decisiones:
- El identificador del colegio se deriva de su codigo con `tukit_comun.derivar`, no se inventa: los
  cargadores de Identidad y de Catalogo llegan al mismo UUID sin hablarse, porque entre las dos
  bases no hay llave foranea.
- `Problema` e `Informe` se repiten en Catalogo a proposito: ningun servicio importa codigo de otro
  y son piezas de presentacion, no dominio compartido.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tukit_comun import derivar

SEDE_POR_OMISION = "Sede unica"


@dataclass(frozen=True)
class Problema:

    bloqueante: bool
    clase: str
    detalle: str

    def __str__(self) -> str:
        marca = "BLOQUEA" if self.bloqueante else "carencia"
        return f"[{marca}] {self.clase}: {self.detalle}"


@dataclass
class Informe:

    escritos: dict[str, int] = field(default_factory=dict)
    problemas: list[Problema] = field(default_factory=list)
    carencias: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def bloqueado(self) -> bool:
        return any(p.bloqueante for p in self.problemas)

    def imprimir(self) -> None:
        print("\n=== sembrado ===")
        for tabla, n in self.escritos.items():
            print(f"  {tabla:24} {n:5}")

        bloqueantes = [p for p in self.problemas if p.bloqueante]
        if bloqueantes:
            print(f"\n=== {len(bloqueantes)} problema(s) que BLOQUEAN ===")
            for p in bloqueantes[:20]:
                print(f"  {p}")
            if len(bloqueantes) > 20:
                print(f"  ... y {len(bloqueantes) - 20} mas")

        if self.carencias:
            print("\n=== lo que falta para poder mostrarlo a un papa ===")
            for que, (faltan, total) in sorted(self.carencias.items()):
                pct = 100 * faltan / total if total else 0
                print(f"  {que:38} {faltan:5}/{total:<5} ({pct:.0f}%)")

        otros = [p for p in self.problemas if not p.bloqueante]
        if otros:
            print(f"\n=== {len(otros)} carencia(s) con nombre propio ===")
            for p in otros[:15]:
                print(f"  {p}")
            if len(otros) > 15:
                print(f"  ... y {len(otros) - 15} mas")


def id_colegio(codigo: str) -> uuid.UUID:
    return derivar("colegio", codigo)


def id_sede(codigo: str, sede_nombre: str) -> uuid.UUID:
    return derivar("sede", codigo, sede_nombre)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _texto(crudo: str | None) -> str:
    return (crudo or "").strip()


def es_nombre_de_relleno(codigo: str, nombre: str) -> bool:
    return nombre == f"Colegio {codigo}"


class Cargador:
    def __init__(self, directorio: Path) -> None:
        self.dir = directorio
        self.problemas: list[Problema] = []
        self.carencias: dict[str, tuple[int, int]] = {}

    def armar(self) -> dict[str, list[dict[str, Any]]]:
        filas = leer_csv(self.dir / "colegios.csv")
        if not filas:
            self.problemas.append(Problema(True, "datos", f"no hay colegios.csv en {self.dir} o esta vacio"))
            return {"colegio": [], "sede": []}

        colegios: list[dict[str, Any]] = []
        sedes: list[dict[str, Any]] = []
        vistos: dict[str, int] = {}

        for numero, fila in enumerate(filas, start=2):
            codigo = _texto(fila.get("codigo"))
            if not codigo:
                self.problemas.append(Problema(True, "codigo", f"fila {numero} sin codigo de colegio"))
                continue
            if codigo in vistos:
                self.problemas.append(
                    Problema(True, "codigo", f"`{codigo}` repetido en las filas {vistos[codigo]} y {numero}")
                )
                continue
            vistos[codigo] = numero

            nombre = _texto(fila.get("nombre")) or f"Colegio {codigo}"
            sede_nombre = _texto(fila.get("sede_nombre")) or SEDE_POR_OMISION
            if not _texto(fila.get("sede_nombre")):
                self.problemas.append(
                    Problema(False, "sede", f"`{codigo}` sin sede declarada: se asume `{SEDE_POR_OMISION}`")
                )

            colegios.append(
                {
                    "id": id_colegio(codigo),
                    "nombre": nombre,
                    "nit": None,
                    "activo": True,
                }
            )
            sedes.append(
                {
                    "id": id_sede(codigo, sede_nombre),
                    "colegio_id": id_colegio(codigo),
                    "nombre": sede_nombre,
                    "activa": True,
                }
            )

        self._medir_carencias(list(vistos), colegios)
        return {"colegio": colegios, "sede": sedes}

    def _medir_carencias(self, codigos: list[str], colegios: list[dict[str, Any]]) -> None:
        total = len(colegios)
        if not total:
            return
        self.carencias["colegios sin nombre propio"] = (
            sum(
                1
                for codigo, colegio in zip(codigos, colegios, strict=True)
                if es_nombre_de_relleno(codigo, colegio["nombre"])
            ),
            total,
        )
        self.carencias["colegios sin NIT"] = (sum(1 for c in colegios if not c["nit"]), total)

    async def escribir(self, datos: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        from sqlalchemy.dialects.postgresql import insert
        from tukit_comun.bd import crear_motor

        from .modelos import Base

        motor = crear_motor("identidad")
        escritos: dict[str, int] = {}
        try:
            async with motor.engine.begin() as conexion:
                for tabla in ("colegio", "sede"):
                    filas = datos.get(tabla, [])
                    if not filas:
                        escritos[tabla] = 0
                        continue
                    objeto = Base.metadata.tables[tabla]
                    sentencia = insert(objeto).values(filas)
                    actualizables = {
                        c.name: sentencia.excluded[c.name]
                        for c in objeto.columns
                        if c.name not in [k.name for k in objeto.primary_key.columns] and c.name in filas[0]
                    }
                    if actualizables:
                        sentencia = sentencia.on_conflict_do_update(
                            index_elements=[c.name for c in objeto.primary_key.columns],
                            set_=actualizables,
                        )
                    else:
                        sentencia = sentencia.on_conflict_do_nothing()
                    await conexion.execute(sentencia)
                    escritos[tabla] = len(filas)
        finally:
            await motor.cerrar()
        return escritos


async def _principal(directorio: Path, solo_validar: bool) -> int:
    cargador = Cargador(directorio)
    datos = cargador.armar()

    informe = Informe(
        escritos={t: len(f) for t, f in datos.items()},
        problemas=cargador.problemas,
        carencias=cargador.carencias,
    )

    if informe.bloqueado:
        print("No se escribio nada: hay codigos de colegio rotos o repetidos.")
        informe.imprimir()
        return 1

    if not solo_validar:
        informe.escritos = await cargador.escribir(datos)

    informe.imprimir()
    if solo_validar:
        print("\n(--solo-validar: no se escribio nada en la base)")
    else:
        print("\nLas listas de estos colegios las siembra Catalogo, contra los mismos UUID.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--datos", type=Path, default=Path("datos/listas"))
    analizador.add_argument("--solo-validar", action="store_true")
    args = analizador.parse_args()

    directorio = args.datos
    if not directorio.exists():
        print(f"No existe el directorio de datos: {directorio}")
        return 2

    return asyncio.run(_principal(directorio, args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
